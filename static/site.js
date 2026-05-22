document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".service-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const detail = document.getElementById(`${button.dataset.service}-detail`);
      if (!detail) return;
      const isHidden = detail.hasAttribute("hidden");
      detail.toggleAttribute("hidden", !isHidden);
      button.textContent = isHidden ? "Hide Details" : "More Details";
    });
  });

  const message = document.getElementById("contact-message");
  const count = document.getElementById("message-count");
  if (message && count) {
    const updateCount = () => {
      count.textContent = `${message.value.length} characters`;
    };
    message.addEventListener("input", updateCount);
    updateCount();
  }
});
