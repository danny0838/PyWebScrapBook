/**
 * Basic implementation of the sort feature.
 * Supports ES3, but not IE < 9.
 */
var dataTable;

document.addEventListener("DOMContentLoaded", function () {
  dataTable = document.getElementById("data-table");
  var head_row = dataTable.tHead.rows[0];
  for (var i = 0, I = head_row.cells.length; i < I; i++) {
    var elem = head_row.cells[i];
    elem.setAttribute("data-orderby", i);
    elem.addEventListener("click", onDataTableHeaderClick, false);
  }
}, false);

function orderBy(column, order) {
  if (typeof order === "undefined") {
    order = (dataTable.getAttribute("data-order") == 1) ? -1 : 1;
  }

  dataTable.setAttribute("data-orderby", column);
  dataTable.setAttribute("data-order", order);

  var keyFuncForColumn = [
    function (k) { return k.toLowerCase(); },
    function (k) { return k.toLowerCase(); },
    function (k) { return parseFloat(k) || 0; },
    function (k) { return parseInt(k) || 0; }
  ];

  var tbody = dataTable.tBodies[0];
  var rows = Array.prototype.slice.call(tbody.rows);

  rows.sort(function (a, b) {
    var ka = a.cells[column].getAttribute("data-sort") || "";
    var kb = b.cells[column].getAttribute("data-sort") || "";
    ka = keyFuncForColumn[column](ka);
    kb = keyFuncForColumn[column](kb);

    if (ka < kb) {
      return -order;
    }
    if (ka > kb) {
      return order;
    }
    return 0;
  });

  for (var i = 0, I = rows.length; i < I; i++) {
    tbody.appendChild(rows[i]);
  }
}

function onDataTableHeaderClick(event) {
  orderBy(parseInt(event.currentTarget.getAttribute('data-orderby'), 10));
}
