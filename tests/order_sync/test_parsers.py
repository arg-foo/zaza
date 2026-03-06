"""Tests for order_sync.parsers — trade plan XML + Tiger text parsers."""

from __future__ import annotations

import pytest

from order_sync.parsers import (
    TradePlan,
    _extract_text,
    _parse_dollar_value,
    parse_open_orders,
    parse_positions,
    parse_trade_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_TRADE_XML = """\
<trade-plan ticker="AAPL" generated="2026-02-24 14:30 UTC">
  <summary>
    <side>BUY</side>
    <ticker>AAPL</ticker>
    <quantity>50</quantity>
    <conviction>HIGH</conviction>
    <expected_value>+3.8%</expected_value>
    <risk_reward_ratio>1:2.5</risk_reward_ratio>
    <rationale>RSI bouncing off 38 with bullish MACD crossover</rationale>
  </summary>
  <order>
    <order_id>BUY-AAPL-20260224-001</order_id>
    <entry>
      <status>PENDING</status>
      <strategy>support_bounce</strategy>
      <trigger>Price holds above $183.50</trigger>
      <limit-order>
        <type>LIMIT</type>
        <side>BUY</side>
        <ticker>AAPL</ticker>
        <quantity>50</quantity>
        <limit_price>184.00</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </entry>
    <exit>
      <stop-loss>
        <limit-order>
          <type>STOP_LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <stop_price>180.00</stop_price>
          <limit_price>179.50</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </stop-loss>
      <take-profit>
        <limit-order>
          <type>LIMIT</type>
          <side>SELL</side>
          <ticker>AAPL</ticker>
          <quantity>50</quantity>
          <limit_price>194.50</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </take-profit>
    </exit>
  </order>
</trade-plan>
"""

COMPLETED_TRADE_XML = """\
<trade-plan ticker="MSFT" generated="2026-02-25 10:00 UTC">
  <summary>
    <side>BUY</side>
    <ticker>MSFT</ticker>
    <quantity>30</quantity>
    <conviction>MEDIUM</conviction>
    <expected_value>+2.1%</expected_value>
    <risk_reward_ratio>1:2.0</risk_reward_ratio>
    <rationale>Momentum breakout above resistance</rationale>
  </summary>
  <order>
    <order_id>BUY-MSFT-20260225-001</order_id>
    <entry>
      <status>COMPLETED</status>
      <strategy>breakout_buy</strategy>
      <trigger>Price breaks above $420.00</trigger>
      <limit-order>
        <type>LIMIT</type>
        <side>BUY</side>
        <ticker>MSFT</ticker>
        <quantity>30</quantity>
        <limit_price>420.50</limit_price>
        <time_in_force>DAY</time_in_force>
      </limit-order>
    </entry>
    <exit>
      <stop-loss>
        <limit-order>
          <type>STOP_LIMIT</type>
          <side>SELL</side>
          <ticker>MSFT</ticker>
          <quantity>30</quantity>
          <stop_price>410.00</stop_price>
          <limit_price>409.50</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </stop-loss>
      <take-profit>
        <limit-order>
          <type>LIMIT</type>
          <side>SELL</side>
          <ticker>MSFT</ticker>
          <quantity>30</quantity>
          <limit_price>440.00</limit_price>
          <time_in_force>DAY</time_in_force>
        </limit-order>
      </take-profit>
    </exit>
  </order>
</trade-plan>
"""

POSITIONS_TEXT = """\
Current Positions
=================

AAPL
  Quantity: 50
  Avg Cost: $184.00
  Market Value: $9,500.00
  Unrealized P&L: $300.00 (3.26%)

MSFT
  Quantity: 30
  Avg Cost: $420.50
  Market Value: $12,900.00
  Unrealized P&L: -$285.00 (-2.16%)
"""

OPEN_ORDERS_TEXT = """\
Open Orders
===========
Order 12345: AAPL BUY 50 (filled 0) | type=LIMIT limit=184.00 status=SUBMITTED
Order 12346: MSFT SELL 30 (filled 0) | type=LIMIT limit=440.00 status=SUBMITTED
Order 12347: MSFT SELL 30 (filled 0) | type=STOP_LIMIT limit=409.50 status=SUBMITTED
"""


# ---------------------------------------------------------------------------
# parse_trade_plan tests
# ---------------------------------------------------------------------------


class TestParseTradePlan:
    """Tests for parsing the new trade plan XML schema."""

    def test_valid_pending_plan(self) -> None:
        """Parse a valid PENDING trade plan XML."""
        plan = parse_trade_plan(VALID_TRADE_XML)
        assert plan is not None
        assert plan.ticker == "AAPL"
        assert plan.side == "BUY"
        assert plan.quantity == 50
        assert plan.order_id == "BUY-AAPL-20260224-001"
        assert plan.entry_status == "PENDING"
        assert plan.entry_limit_price == 184.00
        assert plan.sl_stop_price == 180.00
        assert plan.sl_limit_price == 179.50
        assert plan.tp_limit_price == 194.50

    def test_valid_completed_plan(self) -> None:
        """Parse a valid COMPLETED trade plan XML."""
        plan = parse_trade_plan(COMPLETED_TRADE_XML)
        assert plan is not None
        assert plan.ticker == "MSFT"
        assert plan.side == "BUY"
        assert plan.quantity == 30
        assert plan.order_id == "BUY-MSFT-20260225-001"
        assert plan.entry_status == "COMPLETED"
        assert plan.entry_limit_price == 420.50
        assert plan.sl_stop_price == 410.00
        assert plan.sl_limit_price == 409.50
        assert plan.tp_limit_price == 440.00

    def test_missing_summary_returns_none(self) -> None:
        """XML without <summary> element returns None."""
        xml = '<trade-plan ticker="X"><order><order_id>X</order_id></order></trade-plan>'
        assert parse_trade_plan(xml) is None

    def test_missing_order_returns_none(self) -> None:
        """XML without <order> element returns None."""
        xml = """\
<trade-plan ticker="X">
  <summary>
    <side>BUY</side>
    <ticker>X</ticker>
    <quantity>10</quantity>
  </summary>
</trade-plan>"""
        assert parse_trade_plan(xml) is None

    def test_missing_entry_returns_none(self) -> None:
        """XML with order but no entry returns None."""
        xml = """\
<trade-plan ticker="X">
  <summary><side>BUY</side><ticker>X</ticker><quantity>10</quantity></summary>
  <order><order_id>X-001</order_id></order>
</trade-plan>"""
        assert parse_trade_plan(xml) is None

    def test_missing_exit_returns_none(self) -> None:
        """XML with entry but no exit returns None."""
        xml = """\
<trade-plan ticker="X">
  <summary><side>BUY</side><ticker>X</ticker><quantity>10</quantity></summary>
  <order>
    <order_id>X-001</order_id>
    <entry>
      <status>PENDING</status>
      <limit-order><limit_price>100.00</limit_price></limit-order>
    </entry>
  </order>
</trade-plan>"""
        assert parse_trade_plan(xml) is None

    def test_malformed_xml_returns_none(self) -> None:
        """Malformed XML returns None."""
        assert parse_trade_plan("<not-xml><broken") is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_trade_plan("") is None

    def test_none_input_returns_none(self) -> None:
        """None input returns None."""
        assert parse_trade_plan(None) is None  # type: ignore[arg-type]

    def test_wrong_root_tag_returns_none(self) -> None:
        """XML with wrong root tag returns None."""
        xml = "<something><summary><side>BUY</side></summary></something>"
        assert parse_trade_plan(xml) is None

    def test_non_numeric_quantity_returns_none(self) -> None:
        """Non-numeric quantity in <summary> returns None."""
        xml = VALID_TRADE_XML.replace(
            "<quantity>50</quantity>",
            "<quantity>abc</quantity>",
        )
        assert parse_trade_plan(xml) is None

    def test_plan_id_not_set_by_parser(self) -> None:
        """plan_id should be empty string by default (set externally)."""
        plan = parse_trade_plan(VALID_TRADE_XML)
        assert plan is not None
        assert plan.plan_id == ""


# ---------------------------------------------------------------------------
# Tiger parser tests
# ---------------------------------------------------------------------------


class TestParsePositions:
    """Tests for parsing Tiger positions text."""

    def test_multiple_positions(self) -> None:
        positions = parse_positions(POSITIONS_TEXT)
        assert len(positions) == 2

        aapl = positions[0]
        assert aapl["symbol"] == "AAPL"
        assert aapl["quantity"] == 50
        assert aapl["avg_cost"] == 184.00
        assert aapl["market_value"] == 9500.00
        assert aapl["unrealized_pnl"] == 300.00
        assert aapl["pnl_pct"] == 3.26

        msft = positions[1]
        assert msft["symbol"] == "MSFT"
        assert msft["quantity"] == 30
        assert msft["unrealized_pnl"] == -285.00
        assert msft["pnl_pct"] == -2.16

    def test_no_positions(self) -> None:
        assert parse_positions("No positions found.") == []

    def test_empty_text(self) -> None:
        assert parse_positions("") == []

    def test_single_position(self) -> None:
        text = """\
Current Positions
=================

GOOG
  Quantity: 10
  Avg Cost: $150.00
  Market Value: $1,600.00
  Unrealized P&L: $100.00 (6.67%)
"""
        positions = parse_positions(text)
        assert len(positions) == 1
        assert positions[0]["symbol"] == "GOOG"
        assert positions[0]["quantity"] == 10


class TestParseOpenOrders:
    """Tests for parsing Tiger open orders text."""

    def test_multiple_orders(self) -> None:
        orders = parse_open_orders(OPEN_ORDERS_TEXT)
        assert len(orders) == 3

        assert orders[0]["order_id"] == "12345"
        assert orders[0]["symbol"] == "AAPL"
        assert orders[0]["action"] == "BUY"
        assert orders[0]["quantity"] == 50
        assert orders[0]["filled"] == 0
        assert orders[0]["order_type"] == "LIMIT"
        assert orders[0]["limit_price"] == "184.00"
        assert orders[0]["status"] == "SUBMITTED"

        assert orders[1]["symbol"] == "MSFT"
        assert orders[1]["action"] == "SELL"

    def test_no_open_orders(self) -> None:
        assert parse_open_orders("No open orders.") == []

    def test_empty_text(self) -> None:
        assert parse_open_orders("") == []


class TestParseDollarValue:
    """Tests for dollar value parsing helper."""

    def test_positive(self) -> None:
        assert _parse_dollar_value("$1,234.56") == 1234.56

    def test_negative(self) -> None:
        assert _parse_dollar_value("-$90.00") == -90.00

    def test_invalid(self) -> None:
        assert _parse_dollar_value("abc") == 0.0


class TestExtractText:
    """Tests for MCP response text extraction."""

    def test_with_text_content(self) -> None:
        class FakeContent:
            text = "hello"

        class FakeResponse:
            content = [FakeContent()]

        assert _extract_text(FakeResponse()) == "hello"

    def test_empty_content(self) -> None:
        class FakeResponse:
            content = []

        assert _extract_text(FakeResponse()) == ""

    def test_no_text_attr(self) -> None:
        class FakeContent:
            pass

        class FakeResponse:
            content = [FakeContent()]

        assert _extract_text(FakeResponse()) == ""
