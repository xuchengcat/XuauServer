import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import service_domain_policy as policy


class ServiceDomainPolicyTests(unittest.TestCase):
    def runtime(self):
        return {'rules': list(policy.RULES) + ['MATCH,PROXY'],
                'hosts': {'*.xuchengcat.cn': '192.168.192.1'},
                'dns': {'nameserver-policy': {'+.xuchengcat.cn': '127.0.0.1:53'},
                        'fake-ip-filter-mode': 'whitelist',
                        'fake-ip-filter': ['+.openai.com']}}

    def test_merge_preserves_unrelated_order_and_is_idempotent(self):
        rules = ['DOMAIN-SUFFIX,tmdb.org,MEDIA', policy.RULES[1], 'MATCH,PROXY']
        merged = policy.merge_rules(rules)
        self.assertEqual(merged[:2], policy.RULES)
        self.assertEqual(merged[2:], [rules[0], rules[2]])
        self.assertEqual(policy.merge_rules(merged), merged)

    def test_valid_policy_does_not_mutate_hosts_or_dns(self):
        runtime = self.runtime()
        before = copy.deepcopy(runtime)
        policy.verify(runtime)
        self.assertEqual(runtime, before)

    def test_missing_overridden_or_proxy_rule_is_rejected(self):
        for rules in [policy.RULES[1:], ['DOMAIN-KEYWORD,speedtest,PROXY'] + policy.RULES,
                      [policy.RULES[0].replace('DIRECT','PROXY'), policy.RULES[1]]]:
            runtime = self.runtime()
            runtime['rules'] = rules
            with self.subTest(rules=rules), self.assertRaises(RuntimeError):
                policy.verify(runtime)

    def test_fake_ip_whitelist_conflicts_are_rejected(self):
        for pattern in ['+.xuchengcat.cn', '+.speedtest.xuchengcat.cn', '*',
                        '*.speedtest.xuchengcat.cn', 'jellyfin.speedtest.xuchengcat.cn']:
            runtime = self.runtime()
            runtime['dns']['fake-ip-filter'].append(pattern)
            with self.subTest(pattern=pattern), self.assertRaises(RuntimeError):
                policy.verify(runtime)

    def test_changed_dns_policy_or_mode_is_rejected(self):
        runtime = self.runtime()
        runtime['dns']['nameserver-policy'] = {}
        with self.assertRaises(RuntimeError): policy.verify(runtime)
        runtime = self.runtime()
        runtime['dns']['fake-ip-filter-mode'] = 'blacklist'
        with self.assertRaises(RuntimeError): policy.verify(runtime)

    def test_persistent_check_uses_overrides_not_subscription_nodes(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'yamls').mkdir()
            (base / 'yamls/rules.yaml').write_text(yaml.safe_dump(policy.RULES))
            (base / 'yamls/user.yaml').write_text(yaml.safe_dump(self.runtime()))
            policy.verify_persistent(base)
            (base / 'yamls/rules.yaml').write_text(yaml.safe_dump(['MATCH,PROXY']))
            with self.assertRaises(RuntimeError): policy.verify_persistent(base)

    def test_lock_excludes_second_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(policy, 'LOCK', Path(directory) / 'maintenance.lock'):
                with policy.maintenance_lock():
                    with self.assertRaises(RuntimeError):
                        with policy.maintenance_lock(timeout=0): pass
                with policy.maintenance_lock(timeout=0): pass


if __name__ == '__main__': unittest.main()
