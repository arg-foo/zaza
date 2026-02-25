"""Unit tests for the UserPromptSubmit hook: prompt_context.py.

Tests all pure parsing and formatting functions without requiring
live MCP server connections. Follows TDD red-green-refactor cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: F401

# Add the hook script directory to sys.path so we can import it
_HOOK_DIR = str(
    Path(__file__).resolve().parent.parent.parent / "zaza-agent" / ".claude" / "hooks"
)
if _HOOK_DIR not in sys.path:
    sys.path.insert(0, _HOOK_DIR)

from prompt_context import (  # noqa: E402, I001
    _extract_text,
    _parse_dollar_value,
    cross_reference,
    format_output,
    parse_account_summary,
    parse_open_orders,
    parse_positions,
    parse_trade_plan_xml,
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

TRADE_PLAN_XML_FULL = """\
<trade-plan ticker="AAPL" generated="2026-02-24T14:30:00Z">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
  </summary>
  <conviction>HIGH</conviction>
  <expected-value>+3.8%</expected-value>
  <risk-reward>1:2.5</risk-reward>
  <entry>
    <strategy>support_bounce</strategy>
    <trigger>184.00</trigger>
    <limit-order>
      <order_id>281635863513651</order_id>
      <type>LMT</type>
      <side>BUY</side>
      <ticker>AAPL</ticker>
      <quantity>50</quantity>
      <limit_price>184.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <trigger>179.80</trigger>
      <limit-order>
        <order_id>281635863513835</order_id>
        <type>STP_LMT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>179.50</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <trigger>194.50</trigger>
      <limit-order>
        <order_id>281612463513651</order_id>
        <type>LMT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>194.50</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
"""

TRADE_PLAN_XML_MINIMAL = """\
<trade-plan ticker="TSLA" generated="2026-02-25T09:00:00Z">
  <summary>
    <side>SELL</side>
    <ticker>TSLA</ticker>
    <quantity>10</quantity>
  </summary>
  <entry>
    <strategy>breakdown</strategy>
    <trigger>245.00</trigger>
    <limit-order>
      <order_id>ORDER-001</order_id>
      <type>LMT</type>
      <side>SELL</side>
      <ticker>TSLA</ticker>
      <quantity>10</quantity>
      <limit_price>245.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <trigger>255.00</trigger>
      <limit-order>
        <order_id>ORDER-002</order_id>
        <type>STP_LMT</type>
        <side>BUY</side>
        <ticker>TSLA</ticker>
        <quantity>10</quantity>
        <limit_price>255.50</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <trigger>230.00</trigger>
      <limit-order>
        <order_id>ORDER-003</order_id>
        <type>LMT</type>
        <side>BUY</side>
        <ticker>TSLA</ticker>
        <quantity>10</quantity>
        <limit_price>230.00</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
"""

TRADE_PLAN_XML_MALFORMED = "<trade-plan><summary><side>BUY</side></summary>"


# =====================================================================
# Tests: parse_account_summary
# =====================================================================


class TestParseAccountSummary:
    """Tests for parse_account_summary()."""

    def test_normal_account(self) -> None:
        """Parse standard account summary with positive and negative values."""
        result = parse_account_summary(ACCOUNT_TEXT_NORMAL)

        assert result["cash_balance"] == 12_450.00
        assert result["buying_power"] == 12_450.00
        assert result["realized_pnl"] == 500.00
        assert result["unrealized_pnl"] == -125.30
        assert result["net_liquidation"] == 24_875.20

    def test_negative_cash_balance(self) -> None:
        """Parse account with negative cash and realized PnL."""
        result = parse_account_summary(ACCOUNT_TEXT_NEGATIVE_CASH)

        assert result["cash_balance"] == -3_200.50
        assert result["buying_power"] == 0.00
        assert result["realized_pnl"] == -1_500.75
        assert result["unrealized_pnl"] == -2_300.00
        assert result["net_liquidation"] == 18_499.25

    def test_large_values_with_commas(self) -> None:
        """Parse account with large values containing thousand separators."""
        result = parse_account_summary(ACCOUNT_TEXT_LARGE_VALUES)

        assert result["cash_balance"] == 1_234_567.89
        assert result["buying_power"] == 1_234_567.89
        assert result["realized_pnl"] == 45_678.90
        assert result["unrealized_pnl"] == 12_345.67
        assert result["net_liquidation"] == 2_500_000.00

    def test_returns_all_required_keys(self) -> None:
        """Verify all expected keys are present in the result."""
        result = parse_account_summary(ACCOUNT_TEXT_NORMAL)
        expected_keys = {
            "cash_balance",
            "buying_power",
            "realized_pnl",
            "unrealized_pnl",
            "net_liquidation",
        }
        assert set(result.keys()) == expected_keys


# =====================================================================
# Tests: parse_positions
# =====================================================================


class TestParsePositions:
    """Tests for parse_positions()."""

    def test_multiple_positions(self) -> None:
        """Parse multiple positions with positive and negative PnL."""
        result = parse_positions(POSITIONS_TEXT_MULTIPLE)

        assert len(result) == 2

        aapl = result[0]
        assert aapl["symbol"] == "AAPL"
        assert aapl["quantity"] == 50
        assert aapl["avg_cost"] == 184.00
        assert aapl["market_value"] == 9_325.00
        assert aapl["unrealized_pnl"] == 125.00
        assert aapl["pnl_pct"] == 1.36

        nvda = result[1]
        assert nvda["symbol"] == "NVDA"
        assert nvda["quantity"] == 20
        assert nvda["avg_cost"] == 132.50
        assert nvda["market_value"] == 2_560.00
        assert nvda["unrealized_pnl"] == -90.00
        assert nvda["pnl_pct"] == -3.40

    def test_single_position(self) -> None:
        """Parse a single position."""
        result = parse_positions(POSITIONS_TEXT_SINGLE)

        assert len(result) == 1
        assert result[0]["symbol"] == "TSLA"
        assert result[0]["quantity"] == 10
        assert result[0]["avg_cost"] == 250.00
        assert result[0]["market_value"] == 2_750.00
        assert result[0]["unrealized_pnl"] == 250.00
        assert result[0]["pnl_pct"] == 10.00

    def test_empty_positions(self) -> None:
        """Parse 'No positions found.' returns empty list."""
        result = parse_positions(POSITIONS_TEXT_EMPTY)
        assert result == []

    def test_negative_pnl(self) -> None:
        """Parse position with negative PnL and percentage."""
        result = parse_positions(POSITIONS_TEXT_NEGATIVE_ALL)

        assert len(result) == 1
        meta = result[0]
        assert meta["symbol"] == "META"
        assert meta["unrealized_pnl"] == -1_500.00
        assert meta["pnl_pct"] == -10.00

    def test_position_has_all_keys(self) -> None:
        """Verify each position dict has all expected keys."""
        result = parse_positions(POSITIONS_TEXT_SINGLE)
        expected_keys = {
            "symbol",
            "quantity",
            "avg_cost",
            "market_value",
            "unrealized_pnl",
            "pnl_pct",
        }
        assert set(result[0].keys()) == expected_keys


# =====================================================================
# Tests: parse_open_orders
# =====================================================================


class TestParseOpenOrders:
    """Tests for parse_open_orders()."""

    def test_multiple_orders(self) -> None:
        """Parse multiple orders with different types and statuses."""
        result = parse_open_orders(ORDERS_TEXT_MULTIPLE)

        assert len(result) == 3

        # First order: filled LIMIT BUY
        o1 = result[0]
        assert o1["order_id"] == "281635863513651"
        assert o1["symbol"] == "AAPL"
        assert o1["action"] == "BUY"
        assert o1["quantity"] == 50
        assert o1["filled"] == 50
        assert o1["order_type"] == "LIMIT"
        assert o1["limit_price"] == "184.00"
        assert o1["status"] == "FILLED"

        # Second order: STOP_LIMIT SELL
        o2 = result[1]
        assert o2["order_id"] == "281635863513835"
        assert o2["symbol"] == "AAPL"
        assert o2["action"] == "SELL"
        assert o2["quantity"] == 50
        assert o2["filled"] == 0
        assert o2["order_type"] == "STOP_LIMIT"
        assert o2["limit_price"] == "179.50"
        assert o2["status"] == "NEW"

        # Third order: LIMIT SELL
        o3 = result[2]
        assert o3["order_id"] == "281612463513651"
        assert o3["limit_price"] == "194.50"
        assert o3["status"] == "NEW"

    def test_single_order(self) -> None:
        """Parse a single order line."""
        result = parse_open_orders(ORDERS_TEXT_SINGLE)

        assert len(result) == 1
        assert result[0]["order_id"] == "999888777666555"
        assert result[0]["symbol"] == "TSLA"
        assert result[0]["action"] == "BUY"
        assert result[0]["quantity"] == 10
        assert result[0]["filled"] == 10
        assert result[0]["order_type"] == "LIMIT"
        assert result[0]["status"] == "FILLED"

    def test_empty_orders(self) -> None:
        """Parse 'No open orders.' returns empty list."""
        result = parse_open_orders(ORDERS_TEXT_EMPTY)
        assert result == []

    def test_market_order_na_limit(self) -> None:
        """Parse market order where limit is N/A."""
        result = parse_open_orders(ORDERS_TEXT_MARKET_ORDER)

        assert len(result) == 1
        assert result[0]["order_type"] == "MARKET"
        assert result[0]["limit_price"] == "N/A"

    def test_order_has_all_keys(self) -> None:
        """Verify each order dict has all expected keys."""
        result = parse_open_orders(ORDERS_TEXT_SINGLE)
        expected_keys = {
            "order_id",
            "symbol",
            "action",
            "quantity",
            "filled",
            "order_type",
            "limit_price",
            "status",
        }
        assert set(result[0].keys()) == expected_keys


# =====================================================================
# Tests: parse_trade_plan_xml
# =====================================================================


class TestParseTradePlanXml:
    """Tests for parse_trade_plan_xml()."""

    def test_full_xml_with_optional_fields(self) -> None:
        """Parse trade plan XML with all optional fields present."""
        result = parse_trade_plan_xml(TRADE_PLAN_XML_FULL)

        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["side"] == "BUY"
        assert result["quantity"] == "50"
        assert result["conviction"] == "HIGH"
        assert result["ev"] == "+3.8%"
        assert result["rr"] == "1:2.5"

        assert result["entry"]["strategy"] == "support_bounce"
        assert result["entry"]["trigger"] == "184.00"
        assert result["entry"]["order_id"] == "281635863513651"

        assert result["stop_loss"]["trigger"] == "179.80"
        assert result["stop_loss"]["order_id"] == "281635863513835"

        assert result["take_profit"]["trigger"] == "194.50"
        assert result["take_profit"]["order_id"] == "281612463513651"

    def test_minimal_xml_no_optional_fields(self) -> None:
        """Parse trade plan XML without optional conviction/ev/rr."""
        result = parse_trade_plan_xml(TRADE_PLAN_XML_MINIMAL)

        assert result is not None
        assert result["ticker"] == "TSLA"
        assert result["side"] == "SELL"
        assert result["quantity"] == "10"
        assert result["conviction"] is None
        assert result["ev"] is None
        assert result["rr"] is None

        assert result["entry"]["strategy"] == "breakdown"
        assert result["entry"]["trigger"] == "245.00"
        assert result["entry"]["order_id"] == "ORDER-001"

        assert result["stop_loss"]["order_id"] == "ORDER-002"
        assert result["take_profit"]["order_id"] == "ORDER-003"

    def test_malformed_xml_returns_none(self) -> None:
        """Malformed XML should return None."""
        result = parse_trade_plan_xml(TRADE_PLAN_XML_MALFORMED)
        assert result is None

    def test_completely_invalid_xml(self) -> None:
        """Completely invalid XML string returns None."""
        result = parse_trade_plan_xml("this is not xml at all")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        result = parse_trade_plan_xml("")
        assert result is None

    def test_result_has_all_keys(self) -> None:
        """Verify parsed trade plan has all expected top-level keys."""
        result = parse_trade_plan_xml(TRADE_PLAN_XML_FULL)
        assert result is not None
        expected_keys = {
            "ticker",
            "side",
            "quantity",
            "conviction",
            "ev",
            "rr",
            "entry",
            "stop_loss",
            "take_profit",
        }
        assert set(result.keys()) == expected_keys


# =====================================================================
# Tests: cross_reference
# =====================================================================


class TestCrossReference:
    """Tests for cross_reference()."""

    def test_matching_orders(self) -> None:
        """Plans with matching order IDs get correct order_status."""
        plans = [
            parse_trade_plan_xml(TRADE_PLAN_XML_FULL),
        ]
        open_orders = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        result = cross_reference(plans, open_orders)

        assert len(result) == 1
        plan = result[0]
        assert plan["entry"]["order_status"] == "FILLED"
        assert plan["stop_loss"]["order_status"] == "NEW"
        assert plan["take_profit"]["order_status"] == "NEW"

    def test_unmatched_order_ids(self) -> None:
        """Plans with no matching orders get UNKNOWN status."""
        plans = [
            parse_trade_plan_xml(TRADE_PLAN_XML_MINIMAL),
        ]
        # Minimal plan has ORDER-001, ORDER-002, ORDER-003 which don't match
        open_orders = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        result = cross_reference(plans, open_orders)

        plan = result[0]
        assert plan["entry"]["order_status"] == "UNKNOWN"
        assert plan["stop_loss"]["order_status"] == "UNKNOWN"
        assert plan["take_profit"]["order_status"] == "UNKNOWN"

    def test_empty_orders_list(self) -> None:
        """All plan order statuses should be UNKNOWN when no orders exist."""
        plans = [
            parse_trade_plan_xml(TRADE_PLAN_XML_FULL),
        ]
        result = cross_reference(plans, [])

        plan = result[0]
        assert plan["entry"]["order_status"] == "UNKNOWN"
        assert plan["stop_loss"]["order_status"] == "UNKNOWN"
        assert plan["take_profit"]["order_status"] == "UNKNOWN"

    def test_empty_plans_list(self) -> None:
        """Empty plans list returns empty result."""
        open_orders = parse_open_orders(ORDERS_TEXT_MULTIPLE)
        result = cross_reference([], open_orders)
        assert result == []

    def test_does_not_mutate_original(self) -> None:
        """cross_reference should not mutate the original plan dicts."""
        plan = parse_trade_plan_xml(TRADE_PLAN_XML_FULL)
        assert plan is not None
        original_entry_keys = set(plan["entry"].keys())

        cross_reference([plan], [])

        # Original plan should not have order_status added
        assert "order_status" not in plan["entry"]
        assert set(plan["entry"].keys()) == original_entry_keys

        # Returned plans should have the annotation
        result = cross_reference([parse_trade_plan_xml(TRADE_PLAN_XML_FULL)], [])
        assert result[0]["entry"]["order_status"] == "UNKNOWN"


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
        plan = parse_trade_plan_xml(TRADE_PLAN_XML_FULL)
        assert plan is not None
        plan["plan_id"] = "tp_20260224_143000_123456"
        orders = self._make_orders()
        return cross_reference([plan], orders)

    def test_full_output_is_well_formed_xml(self) -> None:
        """Full output with all sections should be well-formed XML."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )

        # Should parse without error
        root = ET.fromstring(output)
        assert root.tag == "portfolio-context"
        assert root.get("generated") == "2026-02-25T14:30:00Z"

    def test_account_section(self) -> None:
        """Verify account section has correct values."""
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
        """Verify positions section with weight percentages."""
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
        assert aapl.get("avg_cost") == "184.00"
        # current_price = 9325.00 / 50 = 186.50
        assert aapl.get("current_price") == "186.50"
        assert aapl.get("current_value") == "9325.00"
        # weight_pct = 9325.00 / 24875.20 * 100 = 37.5%
        assert aapl.get("weight_pct") is not None
        # Verify it's a reasonable percentage
        weight = float(aapl.get("weight_pct").rstrip("%"))
        assert 37.0 < weight < 38.0

    def test_open_orders_section(self) -> None:
        """Verify open orders section."""
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

        order_elems = orders.findall("order")
        assert len(order_elems) == 3

        o1 = order_elems[0]
        assert o1.get("order_id") == "281635863513651"
        assert o1.get("ticker") == "AAPL"
        assert o1.get("side") == "BUY"
        assert o1.get("type") == "LIMIT"
        assert o1.get("qty") == "50"
        assert o1.get("limit") == "184.00"
        assert o1.get("status") == "FILLED"

    def test_trade_plans_section(self) -> None:
        """Verify active trade plans section with cross-referenced statuses."""
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

        tp = plans.findall("trade-plan")
        assert len(tp) == 1

        plan = tp[0]
        assert plan.get("plan_id") == "tp_20260224_143000_123456"
        assert plan.get("ticker") == "AAPL"
        assert plan.get("side") == "BUY"
        assert plan.get("qty") == "50"
        assert plan.get("conviction") == "HIGH"
        assert plan.get("ev") == "+3.8%"
        assert plan.get("rr") == "1:2.5"

        entry = plan.find("entry")
        assert entry is not None
        assert entry.get("strategy") == "support_bounce"
        assert entry.get("order_id") == "281635863513651"
        assert entry.get("order_status") == "FILLED"

        sl = plan.find("stop-loss")
        assert sl is not None
        assert sl.get("trigger") == "179.80"
        assert sl.get("order_id") == "281635863513835"
        assert sl.get("order_status") == "NEW"

        tp_elem = plan.find("take-profit")
        assert tp_elem is not None
        assert tp_elem.get("trigger") == "194.50"
        assert tp_elem.get("order_id") == "281612463513651"
        assert tp_elem.get("order_status") == "NEW"

    def test_empty_positions(self) -> None:
        """Output with no positions should have count=0."""
        output = format_output(
            account=self._make_account(),
            positions=[],
            open_orders=self._make_orders(),
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        positions = root.find("positions")
        assert positions is not None
        assert positions.get("count") == "0"
        assert len(positions.findall("position")) == 0

    def test_empty_orders(self) -> None:
        """Output with no orders should have count=0."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=[],
            plans=self._make_plans(),
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        orders = root.find("open-orders")
        assert orders is not None
        assert orders.get("count") == "0"

    def test_empty_plans(self) -> None:
        """Output with no plans should have count=0."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=self._make_orders(),
            plans=[],
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        plans = root.find("active-trade-plans")
        assert plans is not None
        assert plans.get("count") == "0"

    def test_plan_without_optional_fields(self) -> None:
        """Trade plan without conviction/ev/rr should omit those attributes."""
        plan = parse_trade_plan_xml(TRADE_PLAN_XML_MINIMAL)
        assert plan is not None
        plan["plan_id"] = "tp_minimal_001"
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
        # Optional attributes should not be present
        assert tp.get("conviction") is None
        assert tp.get("ev") is None
        assert tp.get("rr") is None

    def test_pnl_sign_in_position(self) -> None:
        """Positive PnL should have + prefix, negative should have - prefix."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=[],
            plans=[],
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        pos_elems = root.findall("positions/position")

        # AAPL has positive PnL
        aapl_pnl = pos_elems[0].get("unrealized_pnl")
        assert aapl_pnl is not None
        assert aapl_pnl.startswith("+")

        # NVDA has negative PnL
        nvda_pnl = pos_elems[1].get("unrealized_pnl")
        assert nvda_pnl is not None
        assert nvda_pnl.startswith("-")

    def test_pnl_pct_sign_in_position(self) -> None:
        """PnL percentage should have + or - prefix and end with %."""
        output = format_output(
            account=self._make_account(),
            positions=self._make_positions(),
            open_orders=[],
            plans=[],
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        pos_elems = root.findall("positions/position")

        aapl_pct = pos_elems[0].get("pnl_pct")
        assert aapl_pct is not None
        assert aapl_pct.startswith("+")
        assert aapl_pct.endswith("%")

        nvda_pct = pos_elems[1].get("pnl_pct")
        assert nvda_pct is not None
        assert nvda_pct.startswith("-")
        assert nvda_pct.endswith("%")

    def test_stop_limit_order_has_stop_attribute(self) -> None:
        """STOP_LIMIT orders should include a stop attribute using limit_price."""
        output = format_output(
            account=self._make_account(),
            positions=[],
            open_orders=self._make_orders(),
            plans=[],
            timestamp="2026-02-25T14:30:00Z",
        )

        root = ET.fromstring(output)
        order_elems = root.findall("open-orders/order")

        # Find the STOP_LIMIT order
        stp_order = None
        for o in order_elems:
            if o.get("type") == "STOP_LIMIT":
                stp_order = o
                break

        assert stp_order is not None
        assert stp_order.get("stop") == "179.50"
        assert stp_order.get("limit") == "179.50"


# =====================================================================
# Tests: _parse_dollar_value edge cases (H1)
# =====================================================================


class TestParseDollarValueEdgeCases:
    """Tests for _parse_dollar_value() with invalid inputs."""

    def test_parse_dollar_value_empty_string(self) -> None:
        """Empty string should return 0.0 instead of raising ValueError."""
        result = _parse_dollar_value("")
        assert result == 0.0

    def test_parse_dollar_value_na(self) -> None:
        """'N/A' should return 0.0 instead of raising ValueError."""
        result = _parse_dollar_value("N/A")
        assert result == 0.0

    def test_parse_dollar_value_whitespace_only(self) -> None:
        """Whitespace-only string should return 0.0."""
        result = _parse_dollar_value("   ")
        assert result == 0.0

    def test_parse_dollar_value_normal_still_works(self) -> None:
        """Normal dollar values should still parse correctly."""
        assert _parse_dollar_value("$1,234.56") == 1234.56
        assert _parse_dollar_value("-$500.00") == -500.00
        assert _parse_dollar_value("$0.00") == 0.0


# =====================================================================
# Tests: Float-formatted quantity (H2)
# =====================================================================


class TestFloatQuantity:
    """Tests for parse_positions() with float-formatted quantity strings."""

    def test_float_quantity(self) -> None:
        """Quantity '50.0' should parse to integer 50."""
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
        assert len(result) == 1
        assert result[0]["quantity"] == 50

    def test_float_quantity_with_decimals(self) -> None:
        """Quantity '100.00' should parse to integer 100."""
        text = """\
Current Positions
=================

  TSLA
    Quantity:        100.00
    Avg Cost:        $250.00
    Market Value:    $27,500.00
    Unrealized P&L:  $2,500.00 (10.00%)
"""
        result = parse_positions(text)
        assert len(result) == 1
        assert result[0]["quantity"] == 100


# =====================================================================
# Tests: Empty order_id in trade plan XML (C1)
# =====================================================================


class TestEmptyOrderId:
    """Tests for parse_trade_plan_xml() with empty order_id elements."""

    def test_empty_order_id_returns_none(self) -> None:
        """XML with <order_id></order_id> in entry should return None."""
        xml = """\
<trade-plan ticker="AAPL" generated="2026-02-24T14:30:00Z">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
  </summary>
  <entry>
    <strategy>support_bounce</strategy>
    <trigger>184.00</trigger>
    <limit-order>
      <order_id></order_id>
      <type>LMT</type>
      <side>BUY</side>
      <ticker>AAPL</ticker>
      <quantity>50</quantity>
      <limit_price>184.00</limit_price>
      <time_in_force>DAY</time_in_force>
    </limit-order>
  </entry>
  <exit>
    <stop-loss>
      <trigger>179.80</trigger>
      <limit-order>
        <order_id>ORDER-SL</order_id>
        <type>STP_LMT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>179.50</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </stop-loss>
    <take-profit>
      <trigger>194.50</trigger>
      <limit-order>
        <order_id>ORDER-TP</order_id>
        <type>LMT</type>
        <side>SELL</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>194.50</limit_price>
        <time_in_force>GTC</time_in_force>
      </limit-order>
    </take-profit>
  </exit>
</trade-plan>
"""
        result = parse_trade_plan_xml(xml)
        assert result is None


# =====================================================================
# Tests: Dot/slash tickers like BRK.B (C3)
# =====================================================================


class TestDotSlashTickers:
    """Tests for parse_positions() with tickers containing dots or slashes."""

    def test_positions_with_dot_ticker(self) -> None:
        """Position with BRK.B ticker should be parsed correctly."""
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
        assert result[0]["quantity"] == 15

    def test_positions_with_slash_ticker(self) -> None:
        """Position with BRK/B ticker should be parsed correctly."""
        text = """\
Current Positions
=================

  BRK/B
    Quantity:        10
    Avg Cost:        $400.00
    Market Value:    $4,200.00
    Unrealized P&L:  $200.00 (5.00%)
"""
        result = parse_positions(text)
        assert len(result) == 1
        assert result[0]["symbol"] == "BRK/B"
        assert result[0]["quantity"] == 10

    def test_dot_ticker_alongside_normal_tickers(self) -> None:
        """Mixed dot-ticker and normal tickers should both parse."""
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
# Tests: _extract_text helper (S2)
# =====================================================================


class TestExtractText:
    """Tests for _extract_text() safe content extraction."""

    def test_extract_text_from_empty_response(self) -> None:
        """Response with no content should return empty string."""

        class FakeResponse:
            content = []

        result = _extract_text(FakeResponse())
        assert result == ""

    def test_extract_text_from_none_content(self) -> None:
        """Response with None content should return empty string."""

        class FakeResponse:
            content = None

        result = _extract_text(FakeResponse())
        assert result == ""

    def test_extract_text_from_text_content(self) -> None:
        """Response with text content should return the text."""

        class FakeTextContent:
            text = "hello world"

        class FakeResponse:
            content = [FakeTextContent()]

        result = _extract_text(FakeResponse())
        assert result == "hello world"

    def test_extract_text_from_non_text_content(self) -> None:
        """Response with non-text content (no .text attr) should return empty string."""

        class FakeBinaryContent:
            data = b"\x00\x01\x02"

        class FakeResponse:
            content = [FakeBinaryContent()]

        result = _extract_text(FakeResponse())
        assert result == ""
