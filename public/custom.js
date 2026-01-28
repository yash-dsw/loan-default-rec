document.addEventListener("DOMContentLoaded", function () {
    console.log("Custom JS loaded");

    function injectLogo() {
        // Select the header (Chainlit uses a <header> tag)
        const header = document.querySelector("#header");

        // Find the button with ID new-chat-button
        const newChatBtn = document.querySelector("#new-chat-button");

        console.log("🔍 Checking for header and New Chat icon button...", header, newChatBtn);

        if (header && newChatBtn) {
            console.log("Header and New Chat icon button found");

            // Avoid duplicate logos
            if (document.getElementById("dynamic-logo")) return;

            // Create logo element
            const logo = document.createElement("img");
            logo.src = "/public/dsw.png";
            logo.alt = "Logo";
            logo.id = "dynamic-logo";
            logo.style.height = "120px";
            logo.style.width = "auto";
            logo.style.marginRight = "10px";
            logo.style.cursor = "pointer";

            // Insert logo *before* the new chat icon
            newChatBtn.parentElement.insertBefore(logo, newChatBtn);

            // Apply layout and spacing styles
            const style = document.createElement("style");
            style.textContent = `
        #header {
          display: flex !important;
          align-items: center !important;
          justify-content: space-between !important;
          padding: 8px 20px !important;
          background: #fff !important;
          border-bottom: 1px solid #ddd !important;
          height: 90px !important;
        }

        #header > div:first-child {
          display: flex !important;
          align-items: center !important;
          justify-content: flex-start !important;
          gap: 10px !important;
          flex: 1 !important;
        }

        #header > div:last-child {
          margin-left: auto !important;
        }

        #dynamic-logo {
            position: absolute !important;
            left: 60px !important;
            top: 20px;
            height: 42px !important;
            width: 250px !important;
        }
      `;
            document.head.appendChild(style);

            clearInterval(checkInterval);
        }
    }

    // Keep checking every 500ms until Chainlit UI renders fully
    const checkInterval = setInterval(injectLogo, 500);
});
