# Error codes

Sharewell returns stable codes in `error`. Stop the dependent action when a code appears.

## Input and evidence

| Code | Meaning |
| --- | --- |
| `INVALID_REQUEST` | The CLI request is not a JSON object. |
| `MALFORMED_REQUEST` | A required field, type, or numeric value is malformed. |
| `REQUEST_TOO_LARGE` | The request file exceeds 64 MiB. |
| `DUP_JSON_KEY` | A JSON object repeats a key. |
| `INVALID_SOURCE` | Evidence does not identify the official Binance Agentic MCP endpoint. |
| `STALE_EVIDENCE` | An observation is older than its allowed window or future dated. |
| `MISSING_EVIDENCE` | No host tool-call reference was supplied. |
| `INVALID_EVIDENCE` | An evidence reference is empty, malformed, or too long. |
| `INVALID_SNAPSHOT_VERSION` | The snapshot version is unsupported. |
| `INVALID_DECIMAL_TYPE` | A financial value was not supplied as a decimal string. |
| `INVALID_DECIMAL_TEXT` | A decimal string has invalid syntax. |
| `INVALID_DECIMAL` | Decimal parsing failed. |
| `INVALID_DECIMAL_RANGE` | A decimal is negative or non-finite. |
| `DECIMAL_PRECISION` | A decimal exceeds the supported precision. |
| `INVALID_ASSET` | An asset or symbol identifier is invalid. |

## Snapshot normalization

| Code | Meaning |
| --- | --- |
| `MISSING_CAPTURES` | The normalization request has no capture map. |
| `MISSING_CAPTURE` | A required native result is absent. |
| `MISSING_PAGES` | A capture has no response pages. |
| `INCOMPLETE_CAPTURE` | Pagination was not completed. |
| `MULTIPLE_SINGLE_PAGES` | A non-paginated capture contains multiple pages. |
| `INVALID_MCP_RESULT` | The MCP result envelope is not an object. |
| `MCP_RESULT_ERROR` | The MCP result envelope reports an error. |
| `MCP_PAYLOAD_ERROR` | The normalized payload reports an application error. |
| `BINANCE_API_ERROR` | Binance returned a negative API error code. |
| `INVALID_CONTENT` | The result has neither structured content nor one JSON text block. |
| `INVALID_JSON_TEXT` | A text result is not unambiguous JSON. |
| `NONFINITE_JSON` | JSON contains `NaN` or infinity. |
| `FLOAT_RESULT` | Structured content already rounded a decimal into a binary float. |
| `MCP_DEPTH` | The response nesting limit was exceeded. |
| `INVALID_POINTER` | A response field mapping is not a non-empty JSON Pointer. |
| `INVALID_POINTER_ESCAPE` | A JSON Pointer contains an invalid escape. |
| `EMPTY_POINTER_PART` | A JSON Pointer contains an empty field name. |
| `MISSING_FIELD` | A mapped response field does not exist. |
| `INVALID_ARRAY_INDEX` | A mapped array index is invalid. |
| `POINTER_SCALAR` | A response mapping tries to traverse a scalar. |
| `EXPECTED_ARRAY` | A paginated row capture did not select an array. |
| `EXPECTED_OBJECT_ROW` | A selected row is not an object. |
| `MISSING_FIELD_MAP` | A row mapping omits required fields. |
| `INVALID_ACCOUNT_MAP` | Agentic account mapping must contain `id` and `can_trade`. |
| `INVALID_ACCOUNT_ID` | The authenticated account identifier is missing or invalid. |

## Portfolio and proposal

| Code | Meaning |
| --- | --- |
| `INVALID_ACCOUNT` | Account metadata is not an object. |
| `INVALID_ACCOUNT_KIND` | Account kind is neither Agentic nor main-account read-only. |
| `INVALID_WALLET` | The snapshot is not a Spot wallet. |
| `INVALID_TRADE_PERMISSION` | Trading permission is not an explicit Boolean. |
| `INVALID_BALANCES` | Balances are not an array. |
| `INCOMPLETE_BALANCES` | The full balance set was not captured. |
| `INVALID_BALANCE` | A balance row is malformed. |
| `DUP_BALANCE_ASSET` | The same asset appears more than once. |
| `INVALID_SYMBOLS` | Exchange symbols are not an array. |
| `INVALID_SYMBOL` | A symbol row is malformed. |
| `DUP_SYMBOL` | The same exchange symbol appears more than once. |
| `SELF_PAIR` | A symbol has identical base and quote assets. |
| `INVALID_SYMBOL_FILTERS` | Symbol filters are not an array. |
| `INVALID_QUOTES` | Bid/ask quotes are not an array. |
| `INVALID_QUOTE` | A quote row is malformed. |
| `DUP_QUOTE` | The same symbol has multiple quotes. |
| `INVALID_QUOTE_RANGE` | Bid or ask is non-positive, or bid exceeds ask. |
| `INCOMPLETE_OPEN_ORDERS` | Open Spot orders were not captured completely. |
| `NO_PRICING_ROUTE` | An asset has no available valuation path. |
| `NO_EXECUTABLE_ROUTE` | No locally valid LIMIT route was found. |
| `ROUTE_SEARCH_LIMIT` | Route expansion exceeded 4096 states. |
| `ROUTE_QUEUE_LIMIT` | The bounded route queue filled. |
| `INCOMPLETE_PRICING` | Unpriced assets prevent a complete target allocation. |
| `INVALID_TARGETS` | Target allocations are not an asset-to-percentage map. |
| `INVALID_TARGET_TOTAL` | Target percentages do not total exactly 100. |
| `EMPTY_PORTFOLIO` | The priced portfolio value is zero. |
| `INVALID_BPS` | Fee allowance or slippage is outside the supported range. |
| `INVALID_TTL` | Proposal lifetime is outside 1–300000 milliseconds. |
| `PROPOSAL_LEG_LIMIT` | A proposal would exceed 256 order legs. |
| `ORDER_EXCEEDS_BUDGET` | Rounded order cost exceeds its available source amount. |
| `ROUTE_EXCEEDS_BALANCE` | A route consumes more free balance than available. |
| `INVALID_POLICIES` | Asset policy input is not a supported map or list. |
| `INVALID_POLICY` | An asset policy is not ALLOW or BLOCK. |
| `INVALID_PREFERENCE` | A user preference key is unsupported. |
| `POLICY_CHANGED` | Current hard policy differs from the proposed policy context. |
| `ASSET_NOT_ALLOWED` | An asset is outside the configured allowlist. |
| `BLOCKED_ASSET` | A blocked asset would need to change allocation. |
| `LIVE_SNAPSHOT_REQUIRED` | Snapshot persistence requires an explicit live-evidence gate. |
| `INVALID_SNAPSHOT_REASON` | Snapshot reason is unsupported. |
| `SNAPSHOT_NOT_FOUND` | Persisted portfolio snapshot is missing. |
| `INVALID_HISTORY_LIMIT` | History limit is outside the supported range. |
| `INVALID_EVALUATOR_ID` | Evaluator ID is not stable identifier text. |
| `INVALID_EVALUATOR_VERSION` | Evaluator version is not a positive integer. |
| `INVALID_EVALUATOR_SCOPE` | Evaluator scope is missing or malformed. |
| `INVALID_EVALUATOR_INPUTS` | Evaluator required inputs are malformed. |
| `DUPLICATE_EVALUATOR_INPUT` | Evaluator required inputs repeat a name. |
| `INVALID_EVALUATOR_CONTRACT` | Evaluator does not implement the required contract. |
| `DUPLICATE_EVALUATOR` | Evaluator ID is already registered by another implementation. |
| `UNKNOWN_EVALUATOR` | No evaluator is registered for the requested ID. |
| `INVALID_EVALUATION_INPUT` | Evaluation input is not an object. |
| `MISSING_EVALUATION_INPUT` | A declared evaluator input is absent. |
| `INVALID_EVALUATION_PARAMETERS` | Evaluator parameters failed validation. |
| `INVALID_EVALUATION_RESULT` | Evaluator result is not an object. |
| `INVALID_EVALUATION_STATUS` | Evaluation status is unsupported. |
| `INVALID_EVALUATION_METRICS` | Evaluation metrics are not an object. |
| `INVALID_EVALUATION_EVIDENCE` | Evaluation evidence references are malformed. |
| `INVALID_EVALUATION_WARNINGS` | Evaluation warnings are malformed. |
| `INVALID_EVALUATION_OBSERVATIONS` | Evaluation observations are malformed. |
| `INVALID_EVALUATION_SCORE` | Evaluation score is malformed. |
| `FLOAT_EVALUATION_VALUE` | Evaluation data contains a binary float. |
| `INVALID_EVALUATION_VALUE` | Evaluation data contains an unsupported value. |
| `EVALUATION_NOT_FOUND` | Persisted evaluation run is missing. |
| `EVALUATION_SELECTOR_REQUIRED` | Exactly one evaluator or profile is required. |
| `UNKNOWN_PROFILE` | No evaluation profile is registered for the requested name. |
| `INVALID_PROFILE` | Evaluation profile is malformed. |
| `DUPLICATE_PROFILE` | Evaluation profile name is already registered. |
| `INVALID_PROFILE_PARAMETERS` | Profile parameter overrides are malformed. |
| `INVALID_PRICE_HISTORY` | Historical price input is malformed. |
| `INVALID_EXECUTION_INPUT` | Execution evaluation input is malformed. |
| `INCOMPLETE_EXECUTION_INPUT` | Execution evaluation lacks an authoritative receipt. |
| `NUMERAIRE_MISMATCH` | Outcome inputs use different numeraires. |

## Binance admission checks

| Code | Meaning |
| --- | --- |
| `NEGATIVE_ROUNDING` | A rounding input is negative. |
| `MISSING_QUANTITY_STEP` | Quantity rounding requires a positive step size. |
| `INVALID_SYMBOL_FILTER` | A symbol filter is malformed. |
| `DUP_SYMBOL_FILTER` | A symbol repeats a filter type. |
| `MISSING_CORE_FILTERS` | `PRICE_FILTER` or `LOT_SIZE` is absent. |
| `INVALID_ORDER_SIDE` | Side is not BUY or SELL. |
| `SYMBOL_NOT_TRADABLE` | The symbol cannot accept a Spot LIMIT order. |
| `INVALID_ORDER_AMOUNT` | Quantity or price is non-positive. |
| `INVALID_PERMISSION_SETS` | Symbol permission groups are malformed. |
| `MISSING_ACCOUNT_PERMISSIONS` | Authenticated account permissions were not captured. |
| `INVALID_PERMISSION_GROUP` | A permission group is malformed. |
| `MISSING_SYMBOL_PERMISSION` | The account does not satisfy a permission group. |
| `INVALID_ASSET_FILTER` | An account asset filter is malformed or unsupported. |
| `MAX_ASSET_BASE` | Quantity exceeds an account base-asset cap. |
| `MAX_ASSET_QUOTE` | Notional exceeds an account quote-asset cap. |
| `PRICE_FILTER` | Price violates the symbol price filter. |
| `LOT_SIZE` | Quantity violates the symbol lot-size filter. |
| `MIN_NOTIONAL` | Order notional is below the minimum. |
| `MAX_NOTIONAL` | Order notional exceeds the maximum. |
| `MISSING_FILTER_REFERENCE` | A percentage-price reference was not captured. |
| `INVALID_REFERENCE_BASIS` | A filter reference uses an unknown basis. |
| `INVALID_AVG_WINDOW` | The reference averaging window does not match the filter. |
| `INVALID_PRICE_BASIS` | The fallback price basis does not match Binance rules. |
| `UNVERIFIED_PRICE_FALLBACK` | Absence of a Binance reference price was not proven. |
| `INVALID_FILTER_REFERENCE` | A filter reference price is invalid. |
| `PERCENT_PRICE` | Price violates a percentage-price filter. |
| `MAX_NUM_ORDERS` | The symbol open-order cap is reached. |
| `MAX_POSITION` | A BUY would exceed the base-asset position cap. |
| `UNSUPPORTED_SYMBOL_FILTER` | An applicable symbol filter is not implemented. |
| `EXCHANGE_MAX_NUM_ORDERS` | The exchange-wide open-order cap is reached. |
| `UNSUPPORTED_EXCHANGE_FILTER` | An applicable exchange filter is not implemented. |
| `INVALID_EXECUTION_RULES` | Execution-rule evidence is malformed. |
| `DUP_EXECUTION_RULES` | A symbol repeats its execution-rule entry. |
| `UNSUPPORTED_EXECUTION_RULE` | An unknown execution rule is present. |
| `MISSING_PRICE_RANGE_REF` | PRICE_RANGE exists but its reference response was not captured. |
| `INVALID_PRICE_RANGE_REF` | PRICE_RANGE reference evidence is invalid. |
| `PRICE_RANGE_UNREACHABLE` | The limit makes every possible execution invalid under the observed PRICE_RANGE. |

## Native tool binding

| Code | Meaning |
| --- | --- |
| `INVALID_BIND_INPUT` | Action, account, catalog, or binding is malformed. |
| `INVALID_BIND_OPERATION` | The binding is not for a Spot LIMIT order. |
| `INVALID_TOOL_CATALOG` | The authenticated native tool catalog is malformed. |
| `PLACEMENT_TOOL_NOT_UNIQUE` | The placement tool is missing or ambiguous. |
| `MISSING_TOOL_NAME` | Tool name is absent. |
| `MISSING_TOOL_DESCRIPTION` | Tool semantics were not retained for review. |
| `INVALID_TOOL_ANNOTATIONS` | Tool annotations are malformed. |
| `READ_ONLY_TOOL` | A read-only tool was selected for placement. |
| `INVALID_ACTION_FIELDS` | The action does not contain the exact supported fields. |
| `INVALID_ORDER_MODE` | Only LIMIT IOC is supported. |
| `INVALID_BIND_FIELDS` | Action fields are not mapped exactly once. |
| `OVERLAPPING_BIND` | Native argument paths overlap. |
| `DUPLICATE_BIND` | Two action fields map to the same native field. |
| `INVALID_TOOL_SCHEMA` | Native JSON Schema is absent, malformed, or too deep. |
| `UNSUPPORTED_TOOL_SCHEMA` | The schema contains an unsupported constraint. |
| `INVALID_SCHEMA_REF` | A schema reference is not local. |
| `UNRESOLVED_SCHEMA_REF` | A local schema reference cannot be resolved. |
| `SCHEMA_ALTERNATIVE` | Arguments do not match `anyOf` or `oneOf`. |
| `SCHEMA_ENUM` | An argument is outside the allowed enum. |
| `SCHEMA_CONST` | An argument does not match a constant. |
| `SCHEMA_TYPE` | An argument has the wrong JSON type. |
| `SCHEMA_REQUIRED` | A required native argument is missing. |
| `SCHEMA_EXTRA_FIELD` | The native schema rejects an extra argument. |
| `SCHEMA_STRING_LENGTH` | A string violates its length constraint. |
| `SCHEMA_PATTERN` | A string violates its pattern. |
| `SCHEMA_ARRAY_LENGTH` | An array violates its size constraint. |
| `SCHEMA_MINIMUM` | A number is below its minimum. |
| `SCHEMA_MAXIMUM` | A number exceeds its maximum. |
| `SCHEMA_EXCLUSIVE_MIN` | A number violates its exclusive minimum. |
| `SCHEMA_EXCLUSIVE_MAX` | A number violates its exclusive maximum. |
| `SCHEMA_MULTIPLE` | A number violates its multiple constraint. |
| `LOSSY_NATIVE_NUMBER` | A decimal cannot round-trip exactly through the MCP JSON-number boundary. |

## Approval, dispatch, and verification

| Code | Meaning |
| --- | --- |
| `UNKNOWN_PROPOSAL` | The proposal hash is not in the journal. |
| `PROPOSAL_MISMATCH` | A saved proposal differs from a fresh deterministic recomputation. |
| `INVALID_APPROVAL_STATE` | The proposal is not awaiting approval. |
| `APPROVAL_ACCOUNT_MISMATCH` | Approval names a different account. |
| `PROPOSAL_EXPIRED` | The proposal is outside its approval or dispatch window. |
| `NO_EXECUTABLE_ORDERS` | The proposal cannot be executed. |
| `ACCOUNT_LOCKED` | Another approved proposal owns the account lock. |
| `APPROVAL_REQUIRED` | Dispatch or verification lacks recorded approval. |
| `ACCOUNT_CHANGED` | Fresh pre-dispatch account evidence differs from the approved account. |
| `ORDER_UNRESOLVED` | A previous submission is not a verified full fill. |
| `FEE_REVIEW_REQUIRED` | Recorded commissions require review before another order. |
| `ALL_ORDERS_DISPATCHED` | No undispatched order remains. |
| `STALE_POST_TRADE_BALANCE` | Balance evidence predates the previous dispatch. |
| `SYMBOL_UNAVAILABLE` | Approved symbol metadata is missing from the fresh snapshot. |
| `INSUFFICIENT_FREE_BALANCE` | Free source balance no longer covers the order and fee reserve. |
| `DISPATCH_NOT_FOUND` | No persisted dispatch marker exists for the receipt. |
| `INVALID_ORDER_ID` | The authoritative Binance order ID is absent. |
| `RECEIPT_ACCOUNT_MISMATCH` | Receipt account differs from the proposal account. |
| `CLIENT_ORDER_ID_MISMATCH` | Receipt client ID differs from the persisted client ID. |
| `RECEIPT_BEFORE_DISPATCH` | Receipt observation predates dispatch. |
| `RECEIPT_FIELD_MISMATCH` | Symbol, side, type, or time-in-force differs. |
| `RECEIPT_AMOUNT_MISMATCH` | Receipt price or original quantity differs. |
| `INVALID_ORDER_STATUS` | Binance returned an unsupported order status. |
| `EXECUTED_QTY_EXCEEDED` | Executed quantity exceeds approval. |
| `INCOMPLETE_FILLED_STATUS` | FILLED status does not contain the full approved quantity. |
| `INCOMPLETE_FILLS` | Account trade fills were not captured completely. |
| `FILL_ORDER_MISMATCH` | A fill belongs to another order or symbol. |
| `INVALID_TRADE_ID` | A trade ID is missing or duplicated. |
| `INVALID_FILL_AMOUNT` | Fill quantity or quote amount is non-positive. |
| `FILL_PRICE_VIOLATION` | A fill violates the approved limit. |
| `FILL_TOTAL_MISMATCH` | Fill totals do not match the order totals. |
| `ORDER_ID_CHANGED` | A later receipt changed the Binance order ID. |
| `RECEIPT_REGRESSED` | A later receipt regressed in time or executed quantity. |
| `FILL_HISTORY_CHANGED` | Previously observed fills changed or disappeared. |
| `TERMINAL_RECEIPT_CHANGED` | A terminal receipt changed. |
| `MISSING_ORDER_RECEIPT` | Reconciliation lacks an authoritative receipt. |
| `BALANCE_BEFORE_RECEIPT` | Final balances predate the receipt. |
| `BALANCE_RECONCILIATION_FAILED` | Balance deltas do not equal fills and commissions. |
| `FINAL_ACCOUNT_MISMATCH` | Final balances belong to another account. |
| `EXECUTION_INCOMPLETE` | Not every approved order is a verified full fill. |
| `ACCOUNT_MISMATCH` | Stop evidence belongs to another account. |
| `PROPOSAL_CLOSED` | A closed proposal cannot be stopped again. |
| `THIRD_ASSET_FEE` | Commission was paid in an asset not valued by the approved order. |
| `FEE_ALLOWANCE_EXCEEDED` | Actual commission exceeds the approved allowance. |

## Runtime and packaging

| Code | Meaning |
| --- | --- |
| `MISSING_STATE` | A journal path is required for the operation. |
| `UNKNOWN_OPERATION` | The requested CLI operation is unsupported. |
| `STORAGE_ERROR` | File or SQLite access failed. Preserve unresolved journal state. |
| `RUNTIME_MISSING` | The installed skill bundle lacks its runtime. |
| `SKILL_EXISTS` | The generic installer refuses to overwrite an existing skill. |
| `INSTALL_FAILED` | Generic skill installation failed. |
| `ZIP_EXISTS` | Release packaging refuses to overwrite an existing ZIP. |
| `PATH_ESCAPE` | A package candidate resolves outside the source root. |
| `MISSING_RELEASE_FILES` | Required source files are absent. |
| `PACKAGE_FAILED` | Release packaging failed. |

`BINANCE_CONFIRMATION_REQUIRED`, `SUBMIT_ONCE_THEN_QUERY`, and `NEW_PROPOSAL_REQUIRED` are action codes, not success claims.
