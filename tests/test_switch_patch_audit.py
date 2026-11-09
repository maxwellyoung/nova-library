import unittest
from tools import switch_patch_audit as audit

BUILD = 'A1' * 16
TITLE = '0100000000001000'
PATCH = ('@nsobid-' + BUILD + '\n# Synthetic game [' + TITLE + '] v1.0.0\n'
         '@flag offset_shift 0x100\n@enabled\n00001000 AABBCCDD\n@stop\n').encode()


class SwitchPatchAuditTests(unittest.TestCase):
    def test_exact_identity_is_only_a_source_candidate_and_never_a_device_pass(self):
        r = audit.preview(PATCH, '1.0.0.pchtxt', TITLE, '1.0.0', BUILD.lower())
        self.assertTrue(r['sourceCandidate'])
        self.assertFalse(r['deviceApplied']);self.assertFalse(r['gameplayVerified'])
        self.assertFalse(r['patch']['runtimeTested'])
        self.assertEqual(r['patch']['nsoBuildId'], BUILD + '0' * 32)
        self.assertTrue(audit.preview(PATCH.replace(b'\n', b'\r\n'), '1.0.0.pchtxt', TITLE, '1.0.0', BUILD)['sourceCandidate'])

    def test_version_program_and_build_each_require_exact_matches(self):
        for values in [(TITLE, '1.0.1', BUILD), ('0100000000002000', '1.0.0', BUILD), (TITLE, '1.0.0', 'B2' * 16)]:
            r = audit.preview(PATCH, '1.0.0.pchtxt', *values)
            self.assertFalse(r['sourceCandidate']);self.assertEqual(len(r['identityMismatches']), 1)

    def test_missing_or_conflicting_headers_never_match_by_title(self):
        for data in [PATCH.replace(('[' + TITLE + ']').encode(), b''), PATCH + b'@nsobid-' + BUILD.encode(), PATCH.replace(BUILD.encode(), b'00' * 16)]:
            self.assertTrue(audit.inspect(data, '1.0.0.pchtxt')['issues'])

    def test_mixed_case_flags_are_visible_instead_of_silently_normalised(self):
        data = PATCH.replace(b'@flag', b'@Flag').replace(b'@stop', b'@Stop')
        r = audit.preview(data, '1.0.0.pchtxt', TITLE, '1.0.0', BUILD)
        self.assertIn('unsupported-or-case-mismatched-directive', r['patch']['issues'])
        self.assertFalse(r['sourceCandidate'])

    def test_duplicate_and_partially_overlapping_writes_require_review(self):
        for extra in [b'00001000 AABBCCDD\n', b'00001002 AABB\n']:
            r = audit.inspect(PATCH.replace(b'@stop', extra + b'@stop'), '1.0.0.pchtxt')
            self.assertIn('overlapping-writes-require-review', r['issues'])

    def test_disabled_writes_are_not_claimed_as_enabled(self):
        r = audit.inspect(PATCH.replace(b'@enabled', b'@disabled'), '1.0.0.pchtxt')
        self.assertEqual(r['enabledWriteCount'], 0);self.assertIn('no-enabled-writes', r['issues'])

    def test_unsupported_syntax_and_mismatched_versions_refuse(self):
        for before, after in [(b'0x100', b'-0x100'), (b'AABBCCDD', b'ABC'), (b'AABBCCDD', b'"string"'), (b'00001000', b' 00001000')]:
            self.assertTrue(audit.inspect(PATCH.replace(before, after), '1.0.0.pchtxt')['issues'])
        self.assertIn('version-comment-conflict', audit.inspect(PATCH, '1.0.1.pchtxt')['issues'])

    def test_inputs_are_bounded_and_identity_cannot_be_a_path_or_command(self):
        for data in [b'x' * 65537, b'\x00', b'\xff']:
            with self.assertRaises(audit.AuditError):audit.inspect(data, '1.0.0.pchtxt')
        for values in [(TITLE + '\n', '1.0.0', BUILD), (TITLE, '../1.0.0', BUILD), (TITLE, '1.0.0', BUILD + ';exec')]:
            with self.assertRaises(audit.AuditError):audit.identity(*values)

    def test_output_is_deterministic_and_reports_stretch_without_claiming_native_render(self):
        data = PATCH.replace(b'@enabled', b'// Use stretch to window option\n// HUD may be messy\n@enabled')
        self.assertEqual(audit.inspect(data, '1.0.0.pchtxt'), audit.inspect(data, '1.0.0.pchtxt'))
        r = audit.inspect(data, '1.0.0.pchtxt')
        self.assertTrue(r['requiresStretchSetting']);self.assertGreater(len(r['warnings']), 1)

    def test_writes_after_stop_are_not_silently_ignored_by_the_audit(self):
        r = audit.inspect(PATCH + b'00002000 AABBCCDD\n', '1.0.0.pchtxt')
        self.assertIn('patch-content-after-stop-requires-review', r['issues'])
