(() => {
  const storageKey = "homepage-private-bookmarks-visible";
  const visibleClass = "private-bookmarks-visible";

  const setVisible = (visible) => {
    document.documentElement.classList.toggle(visibleClass, visible);
    if (visible) {
      sessionStorage.setItem(storageKey, "true");
    } else {
      sessionStorage.removeItem(storageKey);
    }
  };

  setVisible(sessionStorage.getItem(storageKey) === "true");

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const isTyping =
      target instanceof HTMLElement &&
      (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

    if (!isTyping && event.ctrlKey && event.shiftKey && event.code === "KeyX") {
      event.preventDefault();
      setVisible(!document.documentElement.classList.contains(visibleClass));
    }
  });
})();
