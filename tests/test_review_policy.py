"""Peer review enforcement tests. No GitHub/AWS/network calls."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('review_policy', ROOT / 'scripts/github/review_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
SHA = 'a' * 40
SOURCE = 'b' * 40
TEAM = {'owner': 'operator', 'collaborators': ['peer']}


class FakeGitHub:
    repo = 'operator/project'
    def __init__(self):
        self.pr = {'state': 'open', 'head': {'sha': SHA}, 'base': {'ref': 'main'}, 'user': {'login': 'github-actions[bot]'}}
        self.files = [{'filename': 'deploy/release.json'}]
        self.declaration = {'runId': '123', 'intent': 'release', 'updatedServices': ['member'], 'images': {'member': {'source': SOURCE}}}
        self.run = {'status': 'completed', 'conclusion': 'success', 'head_branch': 'main', 'head_sha': SOURCE,
                    'path': '.github/workflows/build-push.yml', 'repository': {'full_name': self.repo},
                    'actor': {'login': 'operator'}, 'triggering_actor': {'login': 'operator'}}
        self.reviews = []
        self.permission = 'write'
        self.checks = []
        self.writes = []

    def api(self, endpoint, *, method='GET', payload=None):
        if method != 'GET':
            self.writes.append((endpoint, method, payload))
            return {}
        if endpoint == 'pulls/4': return copy.deepcopy(self.pr)
        if endpoint.startswith('contents/'):
            return {'content': base64.b64encode(json.dumps(self.declaration).encode()).decode()}
        if endpoint == 'actions/runs/123': return copy.deepcopy(self.run)
        if endpoint.startswith('collaborators/'): return {'permission': self.permission}
        if endpoint.startswith('commits/'): return {'check_runs': self.checks}
        raise AssertionError(endpoint)

    def pages(self, endpoint):
        if endpoint.endswith('/files'): return self.files
        if endpoint.endswith('/reviews'): return self.reviews
        raise AssertionError(endpoint)

    def approve(self, user='peer', state='APPROVED', sha=SHA, identifier=1):
        self.reviews.append({'id': identifier, 'state': state, 'commit_id': sha, 'user': {'login': user}})


class PeerReviewTests(unittest.TestCase):
    def test_ci_success_without_human_approval_remains_pending(self):
        self.assertEqual(policy.evaluate(FakeGitHub(), 4, TEAM)[1], 'pending')

    def test_initiating_operator_cannot_self_approve_bot_release(self):
        api = FakeGitHub(); api.approve('operator')
        self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'pending')

    def test_accepted_write_teammate_approval_succeeds(self):
        api = FakeGitHub(); api.approve()
        self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'success')

    def test_outside_review_pending_invitation_and_stale_review_do_not_count(self):
        for user, permission, sha in [('stranger', 'write', SHA), ('peer', 'read', SHA), ('peer', 'write', 'c' * 40)]:
            api = FakeGitHub(); api.approve(user, sha=sha); api.permission = permission
            self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'pending')

    def test_dismissed_or_changed_review_revokes_gate(self):
        for state in ('DISMISSED', 'CHANGES_REQUESTED'):
            api = FakeGitHub(); api.approve(); api.approve(state=state, identifier=2)
            self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'pending')

    def test_comment_does_not_revoke_a_still_current_approval(self):
        api = FakeGitHub(); api.approve(); api.approve(state='COMMENTED', identifier=2)
        self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'success')

    def test_untrusted_or_failed_workflow_is_not_approvable(self):
        for changes in ({'head_branch': 'feature'}, {'conclusion': 'failure'}, {'path': 'other.yml'}, {'head_sha': 'd' * 40}):
            api = FakeGitHub(); api.approve(); api.run.update(changes)
            self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'failure')

    def test_pr_supplied_actor_cannot_override_github_run_actor(self):
        api = FakeGitHub(); api.approve('operator'); api.declaration['requestedBy'] = 'stranger'
        self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'pending')

    def test_source_pr_uses_normal_branch_review_protection(self):
        api = FakeGitHub(); api.files = [{'filename': 'app/msa/member/Dockerfile'}]
        self.assertEqual(policy.evaluate(api, 4, TEAM)[1], 'success')

    def test_new_evaluation_does_not_update_a_check_in_an_old_suite(self):
        api = FakeGitHub()
        api.checks = [{'id': 7, 'name': 'release-approval', 'app': {'slug': 'github-actions'}}]
        policy.publish_check(api, SHA, 'pending', 'Waiting for teammate')
        endpoint, method, payload = api.writes[0]
        self.assertEqual((endpoint, method), ('check-runs', 'POST'))
        self.assertEqual(payload['status'], 'in_progress')
        self.assertNotIn('conclusion', payload)
        self.assertEqual(payload['head_sha'], SHA)
        policy.publish_check(api, SHA, 'success', 'Approved by another authorized teammate: peer')
        self.assertEqual(api.writes[-1][1], 'POST')
        self.assertEqual(api.writes[-1][2]['conclusion'], 'success')


if __name__ == '__main__':
    unittest.main()
