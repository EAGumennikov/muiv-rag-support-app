document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-reference-list]");
    if (!root) {
        return;
    }

    const searchInput = root.querySelector("[data-reference-search]");
    const categorySelect = root.querySelector("[data-reference-category]");
    const items = Array.from(root.querySelectorAll("[data-reference-item]"));
    const emptyMessage = root.querySelector("[data-reference-empty]");

    // Фильтрация выполняется полностью на странице: справочники небольшие,
    // поэтому для учебного web-сервиса не нужен отдельный API или сложный поиск.
    function applyFilters() {
        const query = (searchInput?.value || "").trim().toLowerCase();
        const category = categorySelect?.value || "";
        let visibleCount = 0;

        items.forEach((item) => {
            const text = (item.dataset.search || "").toLowerCase();
            const itemCategory = item.dataset.category || "";
            const matchesQuery = !query || text.includes(query);
            const matchesCategory = !category || itemCategory === category;
            const isVisible = matchesQuery && matchesCategory;
            item.classList.toggle("is-hidden", !isVisible);
            if (isVisible) {
                visibleCount += 1;
            }
        });

        if (emptyMessage) {
            emptyMessage.classList.toggle("is-hidden", visibleCount !== 0);
        }
    }

    searchInput?.addEventListener("input", applyFilters);
    categorySelect?.addEventListener("change", applyFilters);
});
