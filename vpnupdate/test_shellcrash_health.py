import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import maintain_shellcrash as maintenance


class ShellCrashHealthTests(unittest.TestCase):
    def test_default_routes_never_become_interface_names(self):
        fixtures = [
            ('default dev pppoe_dial metric 1024', []),
            ('default via fe80::1 dev eth0', ['fe80::1']),
            ('default dev pppoe_dial\ndefault via fe80::1 dev pppoe_dial', ['fe80::1']),
            ('', []),
            ('default via fe80::1 dev eth0\ndefault via fe80::1 dev eth1', ['fe80::1']),
        ]
        script = Path(__file__).parent / 'shellcrash/fw_getlanip.sh'
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'ShellCrash.log').touch()
            for routes, expected in fixtures:
                with self.subTest(routes=routes):
                    result = subprocess.run(['bash', '-c', '''
ip() {
    if [ "$*" = "-6 route show default" ]; then
        printf '%s\\n' "$TEST_ROUTES"
    else
        printf '%s\\n' '192.168.2.0/24 dev br_lan src 192.168.2.1'
    fi
}
. "$SCRIPT"
ipv6_redir=ON
getlanip
printf '%s\\n' "$host_ipv6"
'''], env=dict(os.environ, TMPDIR=directory, TEST_ROUTES=routes, SCRIPT=str(script)),
                        capture_output=True, text=True, check=True)
                    self.assertEqual(result.stdout.split(), ['fe80::/10', 'fd00::/8'] + expected)

    def test_missing_ipv6_guards_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'configs').mkdir()
            (base / 'configs/ShellCrash.cfg').write_text('firewall_mod=nftables\nfirewall_area=2\nipv6_redir=ON\n')
            guards = ['ip6 daddr { ::/127, fe80::/10 } return',
                      'ip6 saddr != { ::1, fe80::/10 } return']
            proxy = 'meta l4proto tcp redirect to :7892'
            with patch.object(maintenance, 'BASE', base), patch.object(maintenance.subprocess, 'run') as run:
                run.return_value.stdout = '\n'.join(guards + [proxy])
                maintenance.verify_firewall()
                for missing in range(3):
                    lines = guards + [proxy]
                    del lines[missing]
                    run.return_value.stdout = '\n'.join(lines)
                    with self.subTest(missing=missing), self.assertRaises(RuntimeError):
                        maintenance.verify_firewall()

    def test_restart_without_root_never_invokes_systemctl(self):
        with patch.object(maintenance.os, 'geteuid', return_value=1000), patch.object(maintenance.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                maintenance.restart()
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
