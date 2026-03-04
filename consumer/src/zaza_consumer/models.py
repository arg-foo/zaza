"""Pydantic models for Tiger broker event stream messages.

Auto-generated from JSON schemas at tiger-brokers-cash-mcp/schemas/events/.
Regenerate with: uv run python scripts/generate_models.py

Payload models use snake_case field names with camelCase aliases to match the
broker's protobuf-derived JSON format.  ``populate_by_name=True`` allows
construction with either convention.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Payload models (auto-generated from JSON schemas)
# ---------------------------------------------------------------------------


class TransactionPayload(BaseModel):
    """Payload for order transaction (execution/fill) events.

    Fields mirror the ``OrderTransactionData`` protobuf exactly (camelCase).
    All fields are optional because protobuf objects may omit any attribute.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = None
    order_id: str | None = Field(None, alias="orderId")
    account: str | None = None
    symbol: str | None = None
    identifier: str | None = None
    multiplier: float | None = None
    action: str | None = None
    market: str | None = None
    currency: str | None = None
    seg_type: str | None = Field(None, alias="segType")
    sec_type: str | None = Field(None, alias="secType")
    filled_price: float | None = Field(None, alias="filledPrice")
    filled_quantity: int | None = Field(None, alias="filledQuantity")
    create_time: int | None = Field(None, alias="createTime")
    update_time: int | None = Field(None, alias="updateTime")
    transact_time: int | None = Field(None, alias="transactTime")
    timestamp: int | None = None


class OrderStatusPayload(BaseModel):
    """Payload for order status change events.

    Fields mirror the ``OrderStatusData`` protobuf exactly (camelCase).
    All fields are optional because protobuf objects may omit any attribute.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = None
    account: str | None = None
    symbol: str | None = None
    identifier: str | None = None
    name: str | None = None
    sec_type: str | None = Field(None, alias="secType")
    market: str | None = None
    currency: str | None = None
    multiplier: float | None = None
    expiry: str | None = None
    strike: str | None = None
    right: str | None = None
    action: str | None = None
    order_type: str | None = Field(None, alias="orderType")
    time_in_force: str | None = Field(None, alias="timeInForce")
    is_long: bool | None = Field(None, alias="isLong")
    outside_rth: bool | None = Field(None, alias="outsideRth")
    total_quantity: int | None = Field(None, alias="totalQuantity")
    total_quantity_scale: int | None = Field(None, alias="totalQuantityScale")
    limit_price: float | None = Field(None, alias="limitPrice")
    stop_price: float | None = Field(None, alias="stopPrice")
    total_cash_amount: float | None = Field(None, alias="totalCashAmount")
    filled_quantity: int | None = Field(None, alias="filledQuantity")
    filled_quantity_scale: int | None = Field(None, alias="filledQuantityScale")
    avg_fill_price: float | None = Field(None, alias="avgFillPrice")
    filled_cash_amount: float | None = Field(None, alias="filledCashAmount")
    commission_and_fee: float | None = Field(None, alias="commissionAndFee")
    realized_pnl: float | None = Field(None, alias="realizedPnl")
    status: str | None = None
    replace_status: str | None = Field(None, alias="replaceStatus")
    cancel_status: str | None = Field(None, alias="cancelStatus")
    can_modify: bool | None = Field(None, alias="canModify")
    can_cancel: bool | None = Field(None, alias="canCancel")
    liquidation: bool | None = None
    error_msg: str | None = Field(None, alias="errorMsg")
    open_time: int | None = Field(None, alias="openTime")
    timestamp: int | None = None
    source: str | None = None
    user_mark: str | None = Field(None, alias="userMark")
    seg_type: str | None = Field(None, alias="segType")
    attr_desc: str | None = Field(None, alias="attrDesc")
    gst: float | None = None


# ---------------------------------------------------------------------------
# Envelope models (manually defined — match Redis stream field layout)
# ---------------------------------------------------------------------------


class TransactionEvent(BaseModel):
    """Full Redis stream event for transaction (execution/fill) changes.

    The publisher writes four fields to the stream: ``account``,
    ``timestamp``, ``received_at``, and ``payload`` (JSON-encoded string).
    """

    account: str
    timestamp: str | None = None
    received_at: str
    payload: TransactionPayload

    @classmethod
    def from_redis_fields(cls, fields: dict[bytes, bytes]) -> TransactionEvent:
        """Deserialize raw Redis stream fields into a typed event."""
        payload = TransactionPayload.model_validate_json(
            fields.get(b"payload", b"{}")
        )
        return cls(
            account=fields.get(b"account", b"").decode(),
            timestamp=fields.get(b"timestamp", b"").decode() or None,
            received_at=fields.get(b"received_at", b"").decode(),
            payload=payload,
        )


class OrderEvent(BaseModel):
    """Full Redis stream event for order status changes.

    Same envelope structure as ``TransactionEvent`` but with an
    ``OrderStatusPayload``.  Ready for future order stream consumption.
    """

    account: str
    timestamp: str | None = None
    received_at: str
    payload: OrderStatusPayload

    @classmethod
    def from_redis_fields(cls, fields: dict[bytes, bytes]) -> OrderEvent:
        """Deserialize raw Redis stream fields into a typed event."""
        payload = OrderStatusPayload.model_validate_json(
            fields.get(b"payload", b"{}")
        )
        return cls(
            account=fields.get(b"account", b"").decode(),
            timestamp=fields.get(b"timestamp", b"").decode() or None,
            received_at=fields.get(b"received_at", b"").decode(),
            payload=payload,
        )
