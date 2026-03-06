<!-- Tiger Brokers Cash MCP -->
<!-- Server: tiger | Transport: stdin/stdout | Tools: 13 | Domains: 5 -->
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

  <!-- Order Management (3) -->
  <tool name="cancel_order"            query="cancel single open order by ID">
    <param name="order_id" type="int" required="yes" />
  </tool>
  <tool name="cancel_all_orders"       query="cancel all open orders" />

  <!-- OCA & Bracket (2) -->
  <tool name="place_oca_order"         query="submit OCA SELL (TP + SL). One leg fills, other auto-cancels. Blocked if safety errors.">
    <param name="symbol"         type="str"   required="yes" description="uppercase ticker" />
    <param name="quantity"       type="int"   required="yes" description="positive integer, <= held shares" />
    <param name="tp_limit_price" type="float" required="yes" description="take-profit limit price, must be > sl_stop_price" />
    <param name="sl_stop_price"  type="float" required="yes" description="stop-loss trigger price, must be >= sl_limit_price" />
    <param name="sl_limit_price" type="float" required="yes" description="stop-loss execution floor" />
  </tool>
  <tool name="place_bracket_order"     query="submit bracket BUY (entry + TP + SL). Entry fills activates OCA pair. Blocked if safety errors.">
    <param name="symbol"            type="str"   required="yes" description="uppercase ticker" />
    <param name="quantity"          type="int"   required="yes" description="positive integer" />
    <param name="entry_limit_price" type="float" required="yes" description="entry BUY limit price" />
    <param name="tp_limit_price"    type="float" required="yes" description="take-profit price, must be > entry_limit_price" />
    <param name="sl_stop_price"     type="float" required="yes" description="stop-loss trigger, must be < entry_limit_price" />
    <param name="sl_limit_price"    type="float" required="yes" description="stop-loss execution floor, must be <= sl_stop_price" />
  </tool>

  <!-- Order Query (3) -->
  <tool name="get_open_orders"         query="list open/partially-filled orders">
    <param name="symbol" type="str" required="no" description="filter by ticker, empty = all" />
  </tool>
  <tool name="get_order_detail"        query="full order details (not completely filled): fills, avg fill price, commissions, status">
    <param name="order_id" type="int" required="yes" />
  </tool>
  <tool name="get_filled_orders"        query="completely filled order details: fills, avg fill price, commissions, status">
    <param name="order_id" type="int" required="yes" />
  </tool>

</tiger-tools>

<order-types>
  <type name="LMT"     requires="limit_price"              description="Limit order. Executes at limit or better." />
  <type name="STP_LMT" requires="stop_price, limit_price"  description="Stop limit. Triggers at stop, fills at limit or better." />
  <type name="OCA"     requires="tp_limit_price, sl_stop_price, sl_limit_price" description="One-Cancels-All. Two SELL legs (TP limit + SL stop-limit). One fills, other auto-cancels." />
  <type name="BRACKET" requires="entry_limit_price, tp_limit_price, sl_stop_price, sl_limit_price" description="Bracket BUY. Entry limit + attached TP/SL OCA pair activates on fill." />
</order-types>

<rule>Cash account only — no margin, no short selling</rule>
