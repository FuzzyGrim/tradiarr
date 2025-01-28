document.addEventListener("DOMContentLoaded", function () {
  const predefinedRange = document.getElementById("predefined-range");
  const startDate = document.getElementById("start-date");
  const endDate = document.getElementById("end-date");

  function updateDatesFromPredefined() {
    const today = new Date();
    let start = new Date();
    let end = new Date();

    switch (predefinedRange.value) {
      case "today":
        break;
      case "yesterday":
        start.setDate(today.getDate() - 1);
        end = new Date(start);
        break;
      case "thisWeek":
        const dayOffset = today.getDay() === 0 ? 6 : today.getDay() - 1;
        start.setDate(today.getDate() - dayOffset);
        break;
      case "last7Days":
        start.setDate(today.getDate() - 6);
        break;
      case "thisMonth":
        start.setDate(1);
        break;
      case "last30Days":
        start.setDate(today.getDate() - 29);
        break;
      case "last90Days":
        start.setDate(today.getDate() - 89);
        break;
      case "thisYear":
        start = new Date(today.getFullYear(), 0, 1);
        break;
      case "last6Months":
        start.setMonth(today.getMonth() - 6);
        break;
      case "last12Months":
        start.setMonth(today.getMonth() - 12);
        break;
      case "allTime":
        start = new Date(1990, 0, 1);
        break;
      case "custom":
        // Custom range - don't update the dates
        return;
    }

    startDate.value = formatDate(start);
    endDate.value = formatDate(end);
  }

  function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  // Event Listeners
  predefinedRange.addEventListener("change", function () {
    updateDatesFromPredefined();
  });

  // New event listeners for date inputs
  startDate.addEventListener("change", function() {
    predefinedRange.value = "custom";
  });

  endDate.addEventListener("change", function() {
    predefinedRange.value = "custom";
  });
});