// Function to toggle visibility of content sections
function toggleContent(element) {
    const content = element.nextElementSibling;
    if (content.style.display === "block") {
        content.style.display = "none";
    } else {
        content.style.display = "block";
    }
}

// Theme toggle functionality
document.addEventListener("DOMContentLoaded", () => {
    const toggleButton = document.getElementById("theme-toggle");
    toggleButton.addEventListener("click", () => {
        document.body.classList.toggle("light-mode");
        toggleButton.textContent = document.body.classList.contains("light-mode")
            ? "Toggle Dark Mode"
            : "Toggle Light Mode";
    });
});