"""Unit tests for the UserPromptSubmit hook: prompt_context.py.

Tests all pure parsing and formatting functions without requiring
live MCP server connections. Follows TDD red-green-refactor cycle.

Note: parse_positions, parse_open_orders, _parse_dollar_value, _extract_text,
and parse_trade_plan are imported from order_sync.parsers. Their core logic
is tested in tests/order_sync/test_parsers.py. This file tests:
  - parse_account_summary (local to prompt_context)
  - cross_reference (rewritten for TradePlan input)
  - format_output (rewritten for new <order>-wrapped schema)
  - Integration: parsing -> cross_reference -> format_output pipeline
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

# Add the hook script directory to sys.path so we can import it
_HOOK_DIR = str(
    Path(__file__).resolve().parent.parent.parent / "zaza-agent" / ".claude" / "hooks"
)
if _HOOK_DIR not in sys.path:
    sys.path.insert(0, _HOOK_DIR)

from order_sync.parsers import (  # noqa: E402
    TradePlan,
    _extract_text,
    _parse_dollar_value,
    parse_open_orders,
    parse_positions,
)
from prompt_context import (  # noqa: E402, I001
    cross_reference,
    format_output,
    parse_account_summary,
)


# =====================================================================
# Fixtures
# =====================================================================


ACCOUNT_TEXT_NORMAL = """\
Account Summary
===============
  Cash Balance:       $12,450.00
  Buying Power:       $12,450.00
  Realized P&L:       $500.00
  Unrealized P&L:     -$125.30
  Net Liquidation:    $24,875.20
"""

ACCOUNT_TEXT_NEGATIVE_CASH = """\
Account Summary
===============
  Cash Balance:       -$3,200.50
  Buying Power:       $0.00
  Realized P&L:       -$1,500.75
  Unrealized P&L:     -$2,300.00
  Net Liquidation:    $18,499.25
"""

ACCOUNT_TEXT_LARGE_VALUES = """\
Account Summary
===============
  Cash Balance:       $1,234,567.89
  Buying Power:       $1,234,567.89
  Realized P&L:       $45,678.90
  Unrealized P&L:     $12,345.67
  Net Liquidation:    $2,500,000.00
"""

POSITIONS_TEXT_MULTIPLE = """\
Current Positions
=================

  AAPL
    Quantity:        50
    Avg Cost:        $184.00
    Market Value:    $9,325.00
    Unrealized P&L:  $125.00 (1.36%)

  NVDA
    Quantity:        20
    Avg Cost:        $132.50
    Market Value:    $2,560.00
    Unrealized P&L:  -$90.00 (-3.40%)
"""

POSITIONS_TEXT_SINGLE = """\
Current Positions
=================

  TSLA
    Quantity:        10
    Avg Cost:        $250.00
    Market Value:    $2,750.00
    Unrealized P&L:  $250.00 (10.00%)
"""

POSITIONS_TEXT_EMPTY = "No positions found."

POSITIONS_TEXT_NEGATIVE_ALL = """\
Current Positions
=================

  META
    Quantity:        30
    Avg Cost:        $500.00
    Market Value:    $13,500.00
    Unrealized P&L:  -$1,500.00 (-10.00%)
"""

ORDERS_TEXT_MULTIPLE = """\
Order 281635863513651: AAPL BUY 50 (filled 50) | type=LIMIT limit=184.00 status=FILLED submitted=2026-02-24 10:30:00
Order 281635863513835: AAPL SELL 50 (filled 0) | type=STOP_LIMIT limit=179.50 status=NEW submitted=2026-02-24 10:31:00
Order 281612463513651: AAPL SELL 50 (filled 0) | type=LIMIT limit=194.50 status=NEW submitted=2026-02-24 10:32:00
"""  # noqa: E501

ORDERS_TEXT_SINGLE = """\
Order 999888777666555: TSLA BUY 10 (filled 10) | type=LIMIT limit=250.00 status=FILLED submitted=2026-02-24 09:00:00
"""  # noqa: E501

ORDERS_TEXT_EMPTY = "No open orders."

ORDERS_TEXT_MARKET_ORDER = """\
Order 111222333444555: MSFT BUY 100 (filled 100) | type=MARKET limit=N/A status=FILLED submitted=2026-02-24 11:00:00
"""  # noqa: E501


def _make_trade_plan(
    plan_id: str = "tp_20260224_143000_123456",
    ticker: str = "AAPL",
    side: str = "BUY",
    quantity: int = 50,
    order_id: str = "BUY-AAPL-20260224-001",
    entry_status: str = "PENDING",
    entry_limit_price: float = 184.00,
    sl_stop_price: float = 180.00,
    sl_limit_price: float = 179.50,
    tp_limit_price: float = 194.50,
    position_status: str = "NONE",
    position_quantity: int = 0,
    position_avg_cost: float = 0.0,
    conviction: str = "HIGH",
    expected_value: str = "+3.8%",
    risk_reward_ratio: str = "1:2.5",
    entry_strategy: str = "support_bounce",
) -> TradePlan:
    return TradePlan(
        plan_id=plan_id,
        ticker=ticker,
        side=side,
        quantity=quantity,
        order_id=order_id,
        entry_status=entry_status,
        entry_limit_price=entry_limit_price,
        sl_stop_price=sl_stop_price,
        sl_limit_price=sl_limit_price,
        tp_limit_price=tp_limit_price,
        position_status=position_status,
        position_quantity=position_quantity,
        position_avg_cost=position_avg_cost,
        conviction=conviction,
        expected_value=expected_value,
        risk_reward_ratio=risk_reward_ratio,
        entry_strategy=entry_strategy,
    )


# =====================================================================
# Tests: parse_account_summary
# =====================================================================


class TestParseAccountSummary:
    """Tests for parse_account_summary()."""

    def test_normal_account(self) -> None:
        result = parse_account_summary(ACCOUNT_TEXT_NORMAL)
        assert result["cash_balance"] == 12_450.00
        assert result["buying_power"] == 12_450.00
        assert result["realized_pnl"] == 500.00
        assert result["unrealized_pnl"] == -125.30
        assert result["net_liquidation"] == 24_875.20

    def test_negative_cash_balance(self) -> None:
        result = parse_account_summary(ACCOUNT_TEXT_NEGATIVE_CASH)
        assert result["cash_balance"] == -3_200.50
        assert result["buying_power"] == 0.00
        assert result["realized_pnl"] == -1_500.75
        assert result["unrealized_pnl"] == -2_300.00
        assert result["net_liquidation"] == 18_499.25

    def test_large_values_with_commas(self) -> None:
        result = parse_account_summary(ACCOUNT_TEXT_LARGE_VALUES)
        assert result["cash_balance"] == 1_234_567.89
        assert result["net_liquidation"] == 2_500_000.00

    def test_returns_all_required_keys(self) -> None:
        result = parse_account_summary(ACCOUNT_TEXT_NORMAL)
        expected_keys = {
            "cash_balance", "buying_power", "realized_pnl",
            "unrealized_pnl", "net_liquidation",
        }
        assert set(result.keys()) == expected_keys


# =====================================================================
# Tests: parse_positions (imported, light integration check)
# =====================================================================


class TestParsePositions:
    """Tests for parse_positions() — imported from order_sync.parsers."""

    def test_multiple_positions(self) -> None:
        result = parse_positions(POSITIONS_TEXT_MULTIPLE)
        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["quantity"] == 50
        assert result[1]["symbol"] == "NVDA"
        assert result[1]["unrealized_pnl"] == -90.00

    def test_empty_positions(self) -> None:
        assert parse_positions(POSITIONS_TEXT_EMPTY) == []

    def test_position_has_all_keys(self) -> None:
        result = parse_positions(POSITIONS_TEXT_SINGLE)
        expected_keys = {"symbol", "quantity", "avg_cost", "market_value", "unrealized_pnl", "pnl_pct"}
        assert set(result[0].keys()) == expected_keys


# =====================================================================
# Tests: parse_open_orders (imported, light integration check)
# =====================================================================


class TestParseOpenOrders:
    """Tests for parse_open_orders() — imported from order_sync.parsers."""

    def test_multiple_orders(self) -> None:
        result = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        assert len(result) == 3
        assert result[0]["order_id"] == "281635863513651"
        assert result[0]["status"] == "FILLED"
        assert result[1]["order_type"] == "STOP_LIMIT"

    def test_empty_orders(self) -> None:
        assert parse_open_orders(ORDERS_TEXT_EMPTY) == []

    def test_market_order_na_limit(self) -> None:
        result = parse_open_orders(ORDERS_TEXT_MARKET_ORDER)
        assert result[0]["limit_price"] == "N/A"


# =====================================================================
# Tests: cross_reference (rewritten for TradePlan input)
# =====================================================================


class TestCrossReference:
    """Tests for cross_reference() with TradePlan dataclass input."""

    def test_matching_order(self) -> None:
        """Plan with matching order_id gets correct order_status."""
        plan = _make_trade_plan(order_id="281635863513651")
        open_orders = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        result = cross_reference([plan], open_orders)

        assert len(result) == 1
        assert result[0]["order_status"] == "FILLED"
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["order_id"] == "281635863513651"

    def test_unmatched_order_id(self) -> None:
        """Plan with no matching order gets UNKNOWN status."""
        plan = _make_trade_plan(order_id="NONEXISTENT-ORDER")
        open_orders = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        result = cross_reference([plan], open_orders)

        assert result[0]["order_status"] == "UNKNOWN"

    def test_empty_orders_list(self) -> None:
        """All plans should get UNKNOWN when no orders exist."""
        plan = _make_trade_plan()
        result = cross_reference([plan], [])
        assert result[0]["order_status"] == "UNKNOWN"

    def test_empty_plans_list(self) -> None:
        """Empty plans list returns empty result."""
        assert cross_reference([], parse_open_orders(ORDERS_TEXT_MULTIPLE)) == []

    def test_preserves_metadata(self) -> None:
        """cross_reference preserves conviction/ev/rr/entry_strategy."""
        plan = _make_trade_plan(conviction="HIGH", expected_value="+3.8%", risk_reward_ratio="1:2.5")
        result = cross_reference([plan], [])

        assert result[0]["conviction"] == "HIGH"
        assert result[0]["ev"] == "+3.8%"
        assert result[0]["rr"] == "1:2.5"
        assert result[0]["entry_strategy"] == "support_bounce"

    def test_none_metadata_when_empty(self) -> None:
        """Empty conviction/ev/rr should become None in output dict."""
        plan = _make_trade_plan(conviction="", expected_value="", risk_reward_ratio="")
        result = cross_reference([plan], [])

        assert result[0]["conviction"] is None
        assert result[0]["ev"] is None
        assert result[0]["rr"] is None

    def test_preserves_price_levels(self) -> None:
        """cross_reference preserves all price levels."""
        plan = _make_trade_plan(
            entry_limit_price=184.00,
            sl_stop_price=180.00,
            sl_limit_price=179.50,
            tp_limit_price=194.50,
        )
        result = cross_reference([plan], [])

        assert result[0]["entry_limit_price"] == 184.00
        assert result[0]["sl_stop_price"] == 180.00
        assert result[0]["sl_limit_price"] == 179.50
        assert result[0]["tp_limit_price"] == 194.50

    def test_preserves_position_data(self) -> None:
        """cross_reference preserves position_status/quantity/avg_cost."""
        plan = _make_trade_plan(
            position_status="HELD", position_quantity=50, position_avg_cost=184.00
        )
        result = cross_reference([plan], [])

        assert result[0]["position_status"] == "HELD"
        assert result[0]["position_quantity"] == 50
        assert result[0]["position_avg_cost"] == 184.00

    def test_position_none_defaults(self) -> None:
        """cross_reference preserves NONE position defaults."""
        plan = _make_trade_plan()
        result = cross_reference([plan], [])

        assert result[0]["position_status"] == "NONE"
        assert result[0]["position_quantity"] == 0
        assert result[0]["position_avg_cost"] == 0.0

    def test_does_not_mutate_original(self) -> None:
        """cross_reference should not mutate the original TradePlan."""
        plan = _make_trade_plan()
        original_plan_id = plan.plan_id
        cross_reference([plan], [])
        assert plan.plan_id == original_plan_id


# =====================================================================
# Tests: format_output
# =====================================================================


class TestFormatOutput:
    """Tests for format_output()."""

    def _make_account(self) -> dict:
        return parse_account_summary(ACCOUNT_TEXT_NORMAL)

    def _make_positions(self) -> list[dict]:
        return parse_positions(POSITIONS_TEXT_MULTIPLE)

    def _make_orders(self) -> list[dict]:
        return parse_open_orders(ORDERS_TEXT_MULTIPLE)

    def _make_plans(self) -> list[dict]:
        plan = _make_trade_plan(order_id="281635863513651")
        orders = self._make_orders()
        return cross_reference([plan], orders)

    def test_full_output_is_well_formed_xml(self) -> None:
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        assert root.tag == "portfolio-context"
        assert root.get("generated") == "2026-02-25T14:30:00Z"

    def test_account_section(self) -> None:
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        acct = root.find("account")
        assert acct is not None
        assert acct.findtext("cash_balance") == "12450.00"
        assert acct.findtext("buying_power") == "12450.00"
        assert acct.findtext("unrealized_pnl") == "-125.30"
        assert acct.findtext("net_liquidation") == "24875.20"
        assert acct.findtext("total_portfolio") == "24875.20"

    def test_positions_section(self) -> None:
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        positions = root.find("positions")
        assert positions is not None
        assert positions.get("count") == "2"

        pos_elems = positions.findall("position")
        assert len(pos_elems) == 2

        aapl = pos_elems[0]
        assert aapl.get("ticker") == "AAPL"
        assert aapl.get("qty") == "50"
        assert aapl.get("current_price") == "186.50"
        weight = float(aapl.get("weight_pct").rstrip("%"))
        assert 37.0 < weight < 38.0

    def test_open_orders_section(self) -> None:
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        orders = root.find("open-orders")
        assert orders is not None
        assert orders.get("count") == "3"

        o1 = orders.findall("order")[0]
        assert o1.get("order_id") == "281635863513651"
        assert o1.get("ticker") == "AAPL"
        assert o1.get("side") == "BUY"
        assert o1.get("type") == "LIMIT"
        assert o1.get("limit") == "184.00"
        assert o1.get("status") == "FILLED"

    def test_trade_plans_section_new_schema(self) -> None:
        """Trade plans should use <order>-wrapped schema with price levels."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        plans = root.find("active-trade-plans")
        assert plans is not None
        assert plans.get("count") == "1"

        plan = plans.findall("trade-plan")[0]
        assert plan.get("plan_id") == "tp_20260224_143000_123456"
        assert plan.get("ticker") == "AAPL"
        assert plan.get("side") == "BUY"
        assert plan.get("qty") == "50"
        assert plan.get("conviction") == "HIGH"
        assert plan.get("ev") == "+3.8%"
        assert plan.get("rr") == "1:2.5"

        # New <order> wrapper
        order = plan.find("order")
        assert order is not None
        assert order.get("order_id") == "281635863513651"
        assert order.get("order_status") == "FILLED"
        assert order.get("entry_status") == "PENDING"

        # Entry with price level
        entry = order.find("entry")
        assert entry is not None
        assert entry.get("strategy") == "support_bounce"
        assert entry.get("limit_price") == "184.00"

        # Stop-loss with price levels
        sl = order.find("stop-loss")
        assert sl is not None
        assert sl.get("stop_price") == "180.00"
        assert sl.get("limit_price") == "179.50"

        # Take-profit with price level
        tp = order.find("take-profit")
        assert tp is not None
        assert tp.get("limit_price") == "194.50"

    def test_trade_plan_position_none(self) -> None:
        """Trade plan with position NONE shows position_status attribute."""
        plan = _make_trade_plan()
        plans = cross_reference([plan], [])
        output = format_output(
            account=self._make_account(), positions=[], open_orders=[],
            plans=plans, timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        tp = root.find("active-trade-plans/trade-plan")
        assert tp is not None
        assert tp.get("position_status") == "NONE"
        assert tp.get("position_qty") is None  # Not shown when NONE
        assert tp.get("position_avg_cost") is None

    def test_trade_plan_position_held(self) -> None:
        """Trade plan with position HELD shows position details."""
        plan = _make_trade_plan(
            position_status="HELD", position_quantity=50, position_avg_cost=184.00,
        )
        plans = cross_reference([plan], [])
        output = format_output(
            account=self._make_account(), positions=[], open_orders=[],
            plans=plans, timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        tp = root.find("active-trade-plans/trade-plan")
        assert tp is not None
        assert tp.get("position_status") == "HELD"
        assert tp.get("position_qty") == "50"
        assert tp.get("position_avg_cost") == "184.00"

    def test_plan_without_optional_fields(self) -> None:
        """Trade plan without conviction/ev/rr should omit those attributes."""
        plan = _make_trade_plan(conviction="", expected_value="", risk_reward_ratio="")
        plans = cross_reference([plan], [])

        output = format_output(
            account=self._make_account(),
            positions=[],
            open_orders=[],
            plans=plans,
            timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        tp = root.find("active-trade-plans/trade-plan")
        assert tp is not None
        assert tp.get("conviction") is None
        assert tp.get("ev") is None
        assert tp.get("rr") is None

    def test_empty_positions(self) -> None:
        output = format_output(
            account=self._make_account(), positions=[], open_orders=self._make_orders(),
            plans=self._make_plans(), timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        assert root.find("positions").get("count") == "0"

    def test_empty_orders(self) -> None:
        output = format_output(
            account=self._make_account(), positions=self._make_positions(), open_orders=[],
            plans=self._make_plans(), timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        assert root.find("open-orders").get("count") == "0"

    def test_empty_plans(self) -> None:
        output = format_output(
            account=self._make_account(), positions=self._make_positions(),
            open_orders=self._make_orders(), plans=[], timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        assert root.find("active-trade-plans").get("count") == "0"

    def test_pnl_sign_in_position(self) -> None:
        output = format_output(
            account=self._make_account(), positions=self._make_positions(),
            open_orders=[], plans=[], timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        pos_elems = root.findall("positions/position")
        assert pos_elems[0].get("unrealized_pnl").startswith("+")
        assert pos_elems[1].get("unrealized_pnl").startswith("-")

    def test_pnl_pct_sign_in_position(self) -> None:
        output = format_output(
            account=self._make_account(), positions=self._make_positions(),
            open_orders=[], plans=[], timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        pos_elems = root.findall("positions/position")
        assert pos_elems[0].get("pnl_pct").startswith("+")
        assert pos_elems[0].get("pnl_pct").endswith("%")
        assert pos_elems[1].get("pnl_pct").startswith("-")

    def test_stop_limit_order_has_stop_attribute(self) -> None:
        output = format_output(
            account=self._make_account(), positions=[], open_orders=self._make_orders(),
            plans=[], timestamp="2026-02-25T14:30:00Z",
        )
        root = ET.fromstring(output)
        order_elems = root.findall("open-orders/order")
        stp_order = next(o for o in order_elems if o.get("type") == "STOP_LIMIT")
        assert stp_order.get("stop") == "179.50"
        assert stp_order.get("limit") == "179.50"


# =====================================================================
# Tests: _parse_dollar_value edge cases
# =====================================================================


class TestParseDollarValueEdgeCases:
    """Tests for _parse_dollar_value() with invalid inputs."""

    def test_empty_string(self) -> None:
        assert _parse_dollar_value("") == 0.0

    def test_na(self) -> None:
        assert _parse_dollar_value("N/A") == 0.0

    def test_whitespace_only(self) -> None:
        assert _parse_dollar_value("   ") == 0.0

    def test_normal_still_works(self) -> None:
        assert _parse_dollar_value("$1,234.56") == 1234.56
        assert _parse_dollar_value("-$500.00") == -500.00


# =====================================================================
# Tests: Float-formatted quantity
# =====================================================================


class TestFloatQuantity:
    """Tests for parse_positions() with float-formatted quantity strings."""

    def test_float_quantity(self) -> None:
        text = """\
Current Positions
=================

  AAPL
    Quantity:        50.0
    Avg Cost:        $184.00
    Market Value:    $9,325.00
    Unrealized P&L:  $125.00 (1.36%)
"""
        result = parse_positions(text)
        assert result[0]["quantity"] == 50


# =====================================================================
# Tests: Dot/slash tickers like BRK.B
# =====================================================================


class TestDotSlashTickers:
    """Tests for parse_positions() with tickers containing dots or slashes."""

    def test_positions_with_dot_ticker(self) -> None:
        text = """\
Current Positions
=================

  BRK.B
    Quantity:        15
    Avg Cost:        $400.00
    Market Value:    $6,300.00
    Unrealized P&L:  $300.00 (5.00%)
"""
        result = parse_positions(text)
        assert len(result) == 1
        assert result[0]["symbol"] == "BRK.B"

    def test_dot_ticker_alongside_normal_tickers(self) -> None:
        text = """\
Current Positions
=================

  AAPL
    Quantity:        50
    Avg Cost:        $184.00
    Market Value:    $9,325.00
    Unrealized P&L:  $125.00 (1.36%)

  BRK.B
    Quantity:        15
    Avg Cost:        $400.00
    Market Value:    $6,300.00
    Unrealized P&L:  $300.00 (5.00%)
"""
        result = parse_positions(text)
        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[1]["symbol"] == "BRK.B"


# =====================================================================
# Tests: _extract_text helper
# =====================================================================


class TestExtractText:
    """Tests for _extract_text() safe content extraction."""

    def test_empty_response(self) -> None:
        class FakeResponse:
            content = []
        assert _extract_text(FakeResponse()) == ""

    def test_none_content(self) -> None:
        class FakeResponse:
            content = None
        assert _extract_text(FakeResponse()) == ""

    def test_text_content(self) -> None:
        class FakeTextContent:
            text = "hello world"
        class FakeResponse:
            content = [FakeTextContent()]
        assert _extract_text(FakeResponse()) == "hello world"

    def test_non_text_content(self) -> None:
        class FakeBinaryContent:
            data = b"\x00\x01\x02"
        class FakeResponse:
            content = [FakeBinaryContent()]
        assert _extract_text(FakeResponse()) == ""
