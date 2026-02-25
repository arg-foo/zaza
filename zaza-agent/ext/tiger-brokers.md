<!-- Tiger Brokers Cash MCP -->
<!-- Server: tiger | Transport: stdin/stdout | Tools: 12 | Domains: 5 -->
<!-- Cash account trading. Tools appear as mcp__tiger__tool_name. -->

<tiger-tools>

  <!-- Account (4) -->
  <tool name="get_account_summary"     query="cash balance, buying power, realized/unrealized P&L, net liquidation value" />
  <tool name="get_buying_power"        query="available buying power and cash balance" />
  <tool name="get_positions"           query="holdings: qty, avg cost, market value, unrealized P&L per position" />
  <tool name="get_transaction_history" query="filled order history, filterable by symbol/date/limit">
    <param name="symbol"     type="str"  required="no"  description="filter by ticker" />
    <param name="start_date" type="str"  required="no"  description="YYYY-MM-DD" />
    <param name="end_date"   type="str"  required="no"  description="YYYY-MM-DD" />
    <param name="limit"      type="int"  required="no"  default="50" />
  </tool>

  <!-- Market Data (1) -->
  <tool name="get_stock_bars"          query="historical OHLCV bars">
    <param name="symbol" type="str" required="yes" description="uppercase ticker" />
    <param name="period" type="str" required="yes" description="1d|1w|1m|3m|6m|1y" />
    <param name="limit"  type="int" required="no"  default="100" />
  </tool>

  <!-- Order Execution (2) -->
  <tool name="preview_stock_order"     query="dry-run order with safety checks, cost estimate, commission">
    <param name="symbol"      type="str"   required="yes" description="uppercase ticker" />
    <param name="action"      type="str"   required="yes" description="BUY|SELL" />
    <param name="quantity"    type="int"   required="yes" description="positive integer" />
    <param name="order_type"  type="str"   required="yes" description="LMT|STP_LMT" />
    <param name="limit_price" type="float" required="yes" description="limit price" />
    <param name="stop_price"  type="float" required="no"  description="required for STP_LMT" />
  </tool>
  <tool name="place_stock_order"       query="execute order with 6 safety checks. blocked if errors exist">
    <param name="symbol"      type="str"   required="yes" description="uppercase ticker" />
    <param name="action"      type="str"   required="yes" description="BUY|SELL" />
    <param name="quantity"    type="int"   required="yes" description="positive integer" />
    <param name="order_type"  type="str"   required="yes" description="LMT|STP_LMT" />
    <param name="limit_price" type="float" required="yes" description="limit price" />
    <param name="stop_price"  type="float" required="no"  description="required for STP_LMT" />
  </tool>

  <!-- Order Management (3) -->
  <tool name="modify_order"            query="modify open order qty/limit/stop price. re-checks safety on increased risk">
    <param name="order_id"    type="int"   required="yes" />
    <param name="quantity"    type="int"   required="no" />
    <param name="limit_price" type="float" required="no" />
    <param name="stop_price"  type="float" required="no" />
  </tool>
  <tool name="cancel_order"            query="cancel single open order by ID">
    <param name="order_id" type="int" required="yes" />
  </tool>
  <tool name="cancel_all_orders"       query="cancel all open orders" />

  <!-- Order Query (2) -->
  <tool name="get_open_orders"         query="list open/partially-filled orders">
    <param name="symbol" type="str" required="no" description="filter by ticker, empty = all" />
  </tool>
  <tool name="get_order_detail"        query="full order details: fills, avg fill price, commissions, status">
    <param name="order_id" type="int" required="yes" />
  </tool>

</tiger-tools>

<order-types>
  <type name="LMT"     requires="limit_price"              description="Limit order. Executes at limit or better." />
  <type name="STP_LMT" requires="stop_price, limit_price"  description="Stop limit. Triggers at stop, fills at limit or better." />
</order-types>

<rule>Cash account only — no margin, no short selling</rule>
