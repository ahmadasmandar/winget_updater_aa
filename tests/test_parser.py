from winget_gui.parser import parse_upgrade_output


def test_parse_english_output():
    output = "Name                 Id                         Version Available Source\n-------------------- -------------------------- ------- --------- ------\nFirefox              Mozilla.Firefox             1.0     2.0       winget\n"
    assert parse_upgrade_output(output)[0]["Id"] == "Mozilla.Firefox"


def test_parse_german_long_name():
    output = "Name                 ID                         Version Verfügbar Quelle\n-------------------- -------------------------- ------- --------- ------\nA very long package  Example.Package             1.0     2.0       winget\n"
    assert parse_upgrade_output(output)[0]["Name"] == "A very long package"


def test_skip_truncated_and_malformed_lines():
    output = "Name                 Id                         Version Available\n-------------------- -------------------------- ------- ---------\nBad                  Example.…                  1.0     2.0\nMalformed            ???                        1.0     2.0\n"
    assert parse_upgrade_output(output) == []

