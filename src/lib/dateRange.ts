function formatDateInputValue(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function addMonthsClamped(value: Date, months: number): Date {
    const targetMonth = value.getMonth() + months;
    const lastDay = new Date(value.getFullYear(), targetMonth + 1, 0).getDate();
    return new Date(value.getFullYear(), targetMonth, Math.min(value.getDate(), lastDay));
}

export function getDefaultDateRange(referenceDate = new Date()) {
    return {
        start: formatDateInputValue(addMonthsClamped(referenceDate, -1)),
        end: formatDateInputValue(addMonthsClamped(referenceDate, 1)),
    };
}
