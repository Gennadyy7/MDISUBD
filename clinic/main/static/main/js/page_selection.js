function handleNavigation(selectElement) {
    const selectedValue = selectElement.value;
    if (selectedValue) {
        window.location.href = selectedValue;
    }
}