"""
sentry.plugins.base.structs
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2013 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import, print_function

__all__ = ['ReleaseHook']

from django.utils import timezone

from datetime import timedelta

from sentry.models import Commit, Release, ReleaseCommit, ReleaseProject, Repository, User
from sentry.plugins import ReleaseHook
from sentry.testutils import TestCase


class StartReleaseTest(TestCase):
    def test_minimal(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'

        hook = ReleaseHook(project)
        hook.start_release(version)

        release = Release.objects.get(
            organization_id=project.organization_id,
            version=version,
        )
        assert release.organization
        assert ReleaseProject.objects.get(release=release, project=project)

    def test_update_release(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'
        r = Release.objects.create(organization_id=project.organization_id, version=version)
        r.add_project(project)

        hook = ReleaseHook(project)
        hook.start_release(version)

        release = Release.objects.get(
            organization_id=project.organization_id,
            projects=project,
            version=version,
        )
        assert release.organization == project.organization


class FinishReleaseTest(TestCase):
    def test_minimal(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'

        hook = ReleaseHook(project)
        hook.finish_release(version)

        release = Release.objects.get(
            organization_id=project.organization_id,
            version=version,
        )
        assert release.date_released
        assert release.organization
        assert ReleaseProject.objects.get(release=release, project=project)

    def test_update_release(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'
        r = Release.objects.create(organization_id=project.organization_id, version=version)
        r.add_project(project)

        hook = ReleaseHook(project)
        hook.start_release(version)

        release = Release.objects.get(
            projects=project,
            version=version,
        )
        assert release.organization == project.organization


class SetCommitsTest(TestCase):
    def test_minimal(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'
        data_list = [
            {
                'id': 'c7155651831549cf8a5e47889fce17eb',
                'message': 'foo',
                'author_email': 'jane@example.com',
            },
            {
                'id': 'bbee5b51f84611e4b14834363b8514c2',
                'message': 'bar',
                'author_name': 'Joe^^',
            },
        ]

        hook = ReleaseHook(project)
        hook.set_commits(version, data_list)

        release = Release.objects.get(
            projects=project,
            version=version,
        )
        commit_list = list(Commit.objects.filter(
            releasecommit__release=release,
        ).select_related(
            'author',
        ).order_by('releasecommit__order'))

        assert len(commit_list) == 2
        assert commit_list[0].key == 'c7155651831549cf8a5e47889fce17eb'
        assert commit_list[0].message == 'foo'
        assert commit_list[0].author.name is None
        assert commit_list[0].author.email == 'jane@example.com'
        assert commit_list[1].key == 'bbee5b51f84611e4b14834363b8514c2'
        assert commit_list[1].message == 'bar'
        assert commit_list[1].author.name == 'Joe^^'
        assert commit_list[1].author.email == 'joe@localhost'


class SetRefsTest(TestCase):
    # test that when finish release gets called with heroku, and a ref
    # that release commits are then associated with release
    def test_minimal(self):
        project = self.create_project()
        version = 'bbee5b51f84611e4b14834363b8514c2'
        data_list = [
            {
                'id': 'c7155651831549cf8a5e47889fce17eb',
                'message': 'foo',
                'author_email': 'jane@example.com',
            },
            {
                'id': '8c3b70eb3b4b15822a27edc797c80fd0dd6092dc',
                'message': 'bar',
                'author_name': 'Joe^^',
            },
            {
                'id': 'bbee5b51f84611e4b14834363b8514c2',
                'message': 'blah',
                'author_email': 'katie@example.com',
            },
        ]
        user = User.objects.create(email='stebe@sentry.io')
        repo = Repository.objects.create(
            organization_id=project.organization_id,
            name=project.name
        )
        for data in data_list:
            Commit.objects.create(
                key=data['id'],
                organization_id=self.project.organization_id,
                repository_id=repo.id
            )

        old_release = Release.objects.create(
            version='a' * 40,
            organization_id=project.organization_id,
            date_added=timezone.now() - timedelta(minutes=30),
        )
        old_release.add_project(self.project)

        ReleaseCommit.objects.create(
            organization_id=project.organization_id,
            project_id=project.id,
            release=old_release,
            commit=Commit.objects.get(key='c7155651831549cf8a5e47889fce17eb'),
        )

        hook = ReleaseHook(project)
        hook.finish_release(version=version,
            owner=user,
            head_commit=version,
            deploy_provider="heroku",
        )

        release = Release.objects.get(
            projects=project,
            version=version,
        )
        commit_list = list(Commit.objects.filter(
            releasecommit__release=release,
        ).select_related(
            'author',
        ).order_by('releasecommit__order'))

        assert len(commit_list) == 2
        assert commit_list[0].key == '8c3b70eb3b4b15822a27edc797c80fd0dd6092dc'
        assert commit_list[0].message == 'bar'
        assert commit_list[1].key == 'bbee5b51f84611e4b14834363b8514c2'
        assert commit_list[1].message == 'blah'
