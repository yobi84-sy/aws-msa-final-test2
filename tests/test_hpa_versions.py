"""HPA wire-version compatibility; no Kubernetes connection or CPU load."""
import copy
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/ops'))
import lab_verify as verify


def v2(replicas=1, cpu=1):
    return {'apiVersion': 'autoscaling/v2',
            'spec': {'minReplicas': 1, 'maxReplicas': 3,
                     'metrics': [{'type': 'Resource', 'resource': {
                         'name': 'cpu', 'target': {'type': 'Utilization', 'averageUtilization': 60}}}]},
            'status': {'currentReplicas': replicas,
                       'currentMetrics': [{'type': 'Resource', 'resource': {
                           'name': 'cpu', 'current': {'averageUtilization': cpu}}}]}}


class HpaVersionTests(unittest.TestCase):
    def test_equivalent_v1_and_v2_target_and_observed_cpu(self):
        legacy = {'spec': {'targetCPUUtilizationPercentage': 60},
                  'status': {'currentCPUUtilizationPercentage': 145}}
        for hpa in (legacy, v2(cpu=145)):
            self.assertEqual(verify.hpa_cpu_percent(hpa), 60)
            self.assertEqual(verify.hpa_cpu_percent(hpa, current=True), 145)

    def test_missing_current_metric_is_unknown_not_zero(self):
        hpa = v2()
        hpa['status'] = {}
        self.assertIsNone(verify.hpa_cpu_percent(hpa, current=True))

    def test_unrecognized_or_additional_metrics_stop_before_load(self):
        cases = []
        for change in ('memory', 'value', 'external', 'additional', 'wrong-target'):
            hpa = v2()
            metric = hpa['spec']['metrics'][0]
            if change == 'memory': metric['resource']['name'] = 'memory'
            if change == 'value': metric['resource']['target']['type'] = 'AverageValue'
            if change == 'external': metric['type'] = 'External'
            if change == 'additional': hpa['spec']['metrics'].append(copy.deepcopy(metric))
            if change == 'wrong-target': metric['resource']['target']['averageUtilization'] = 75
            cases.append(hpa)
        for hpa in cases:
            with self.subTest(hpa=hpa):
                start = Mock()
                with self.assertRaisesRegex(ValueError, 'Unexpected HPA bounds'):
                    verify.scale(SimpleNamespace(kube=lambda *args: hpa), popen=start)
                start.assert_not_called()

    def test_v2_scale_cycle_records_cpu_and_ready_expansion(self):
        readings = iter([v2(), v2(3, 150), v2(1, 1)])
        latest = [None]
        def kube(*args):
            if args[1] == 'hpa':
                latest[0] = next(readings)
                return latest[0]
            if args[1] == 'pods':
                return {'items': [{'metadata': {'name': 'unit'}, 'status': {
                    'conditions': [{'type': 'Ready', 'status': 'True'}]}}]}
            if args[1] == 'deployment':
                return {'status': {'availableReplicas': latest[0]['status']['currentReplicas']}}
            if args[1] == 'nodes': return {'items': [1, 2, 3]}
            raise AssertionError(args)
        child = SimpleNamespace(poll=lambda: 124, returncode=124)
        start = Mock(return_value=child)
        with redirect_stdout(io.StringIO()):
            result = verify.scale(SimpleNamespace(kube=kube, env={}, root=Path.cwd()),
                                  clock=lambda: 0, sleep=lambda seconds: None, popen=start)
        self.assertTrue(result['expandedAndContracted'])
        self.assertEqual([o['cpuPercent'] for o in result['observations']], [150, 1])
        start.assert_called_once()
        self.assertEqual(start.call_args.args[0][-3:], ['180', 'sha256sum', '/dev/zero'])


if __name__ == '__main__':
    unittest.main()
