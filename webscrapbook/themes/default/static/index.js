/**
 * Basic implementation of the sort feature.
 * Supports ES3, but not IE < 9.
 */
(function (globalThis) {

var dataTableHandler = {
  elem: null,
  sortKeyHandlers: {
    string: function (k) { return String(k); },
    string_ci: function (k) { return String(k).toLowerCase(); },
    float: function (k) { return parseFloat(k) || 0; },
    integer: function (k) { return parseInt(k) || 0; }
  },
  init: init,
  orderBy: orderBy,
  onDataTableHeaderClick: onDataTableHeaderClick
};

function init() {
  var table = dataTableHandler.elem = document.getElementById("data-table");
  var headRowCells = table.tHead.rows[0].cells;
  for (var i = 0, I = headRowCells.length; i < I; i++) {
    var elem = headRowCells[i];
    elem.setAttribute("data-orderby", i);
    elem.addEventListener("click", dataTableHandler.onDataTableHeaderClick, false);
  }
}

function orderBy(column, order) {
  var table = dataTableHandler.elem;
  if (typeof order === "undefined") {
    order = (table.getAttribute("data-order") == 1) ? -1 : 1;
  }

  table.setAttribute("data-orderby", column);
  table.setAttribute("data-order", order);

  var sortType = table.tHead.rows[0].cells[column].getAttribute("data-sort-type");
  var sortKeyFunc = dataTableHandler.sortKeyHandlers[sortType] || dataTableHandler.sortKeyHandlers['string'];
  var tbody = table.tBodies[0];
  var rows = Array.prototype.slice.call(tbody.rows);

  rows.sort(function (a, b) {
    var ka = sortKeyFunc(a.cells[column].getAttribute("data-sort") || "");
    var kb = sortKeyFunc(b.cells[column].getAttribute("data-sort") || "");

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
  dataTableHandler.orderBy(parseInt(event.currentTarget.getAttribute('data-orderby'), 10));
}

globalThis.document.addEventListener("DOMContentLoaded", function () {
  dataTableHandler.init();
}, false);

globalThis.dataTableHandler = dataTableHandler;

})(this);
