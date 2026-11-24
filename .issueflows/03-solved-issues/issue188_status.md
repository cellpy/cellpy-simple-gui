# Issue #188 status

- [x] Done

## What's done

- `POST /api/cells/bulk` and `Library.bulk_update`: one field per request, arithmetic on mass / area / nominal capacity, set for group / basis / cycle mode. Unknown ids, division by zero, non-finite operands, and `group < 1` write nothing. A non-positive float result is skipped per cell.
- Manage cells toolbar applies that to checked cells in the current name filter, then defers the replot until the dialog closes.
- API tests cover multiply, set group, unknown id, divide by zero, a skipped non-positive result, an empty id list, and two fields at once.
- Decision recorded in `manage-cells-modal.md`.

## Remaining work

- None. Using this modal to load cells (the comment on #188) stays out of scope, as accepted in the plan.
