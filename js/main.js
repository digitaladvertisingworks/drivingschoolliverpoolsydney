const siteHeader = document.querySelector(".site-header");
const navToggle = document.querySelector(".nav-toggle");
const faqButtons = document.querySelectorAll(".faq-item button");

if (navToggle && siteHeader) {
  navToggle.addEventListener("click", () => {
    const isOpen = siteHeader.classList.toggle("nav-open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });
}

const toggleHeaderShadow = () => {
  if (!siteHeader) {
    return;
  }

  siteHeader.classList.toggle("is-scrolled", window.scrollY > 8);
};

toggleHeaderShadow();
window.addEventListener("scroll", toggleHeaderShadow, { passive: true });

faqButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const panel = button.nextElementSibling;
    const isExpanded = button.getAttribute("aria-expanded") === "true";

    faqButtons.forEach((otherButton) => {
      if (otherButton !== button) {
        otherButton.setAttribute("aria-expanded", "false");
        const otherPanel = otherButton.nextElementSibling;
        if (otherPanel) {
          otherPanel.hidden = true;
        }
      }
    });

    button.setAttribute("aria-expanded", String(!isExpanded));
    if (panel) {
      panel.hidden = isExpanded;
    }
  });
});

// Web3Forms enquiry form: submit in place so the visitor stays on the page.
// Without JS the plain POST still works and Web3Forms shows its own confirmation.
document.querySelectorAll(".enquiry-form").forEach((form) => {
  const status = form.querySelector(".form-status");
  const button = form.querySelector('button[type="submit"]');
  const failure =
    "Sorry, that did not send. Please call (02) 8776 1815 or email info@drivingschoolliverpool.sydney.";

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    status.hidden = true;
    status.classList.remove("is-error");

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { Accept: "application/json" },
        body: new FormData(form)
      });
      const data = await response.json();

      if (data.success) {
        form.reset();
        status.textContent =
          "Thanks, your enquiry has been sent. We will reply during branch hours.";
      } else {
        status.classList.add("is-error");
        status.textContent = failure;
      }
    } catch (error) {
      status.classList.add("is-error");
      status.textContent = failure;
    }

    button.disabled = false;
    status.hidden = false;
  });
});
