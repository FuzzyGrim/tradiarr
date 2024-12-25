$(function () {
  $('input[name="date-range"]').daterangepicker({
    startDate: moment().startOf("year"),
    endDate: moment(),
    minYear: 1990,
    maxYear: moment().year(),
    maxDate: moment(),
    showDropdowns: true,
    alwaysShowCalendars: true,
    linkedCalendars: false,
    opens: "center",
    ranges: {
      Today: [moment(), moment()],
      Yesterday: [moment().subtract(1, "days"), moment().subtract(1, "days")],
      "Last 7 Days": [moment().subtract(6, "days"), moment()],
      "Last 30 Days": [moment().subtract(29, "days"), moment()],
      "This Month": [moment().startOf("month"), moment().endOf("month")],
      "This Year": [moment().startOf("year"), moment().endOf("year")],
      "All Time": [moment().subtract(100, "year"), moment()],
    },
  });
});
