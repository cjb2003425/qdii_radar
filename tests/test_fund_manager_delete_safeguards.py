from pathlib import Path


FUND_MANAGER_PATH = Path(__file__).parent.parent / 'components' / 'FundManager.tsx'


def read_source() -> str:
    return FUND_MANAGER_PATH.read_text(encoding='utf-8')


def test_preset_funds_have_no_single_delete_button_guard():
    source = read_source()
    assert '!isBatchMode && fund.isUserAdded' in source
    assert 'title="删除自定义基金"' in source


def test_preset_fund_single_delete_is_blocked_in_ui_logic():
    source = read_source()
    assert '预设基金不可永久删除' in source
    assert 'if (!fund.isUserAdded)' in source


def test_batch_delete_confirmation_mentions_skipped_preset_funds():
    source = read_source()
    assert 'selectedPresetFunds.length > 0' in source
    assert '预设基金将被跳过' in source
    assert '已删除 ${fundCodes.length} 只自定义基金，跳过 ${selectedPresetFunds.length} 只预设基金' in source


def test_fund_manager_distinguishes_user_and_preset_funds():
    source = read_source()
    assert 'isUserAdded: fund.isUserAdded ?? userFunds.some(uf => uf.code === fund.code)' in source
    assert 'isPreset: fund.isPreset ?? !(fund.isUserAdded ?? userFunds.some(uf => uf.code === fund.code))' in source
