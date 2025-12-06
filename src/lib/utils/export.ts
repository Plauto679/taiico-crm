import * as XLSX from 'xlsx';

export const exportToExcel = (data: any[], fileName: string) => {
    // Create a new workbook
    const workbook = XLSX.utils.book_new();

    // Convert data to worksheet
    const worksheet = XLSX.utils.json_to_sheet(data);

    // Add worksheet to workbook
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1');

    // Write workbook and trigger download
    XLSX.writeFile(workbook, fileName);
};
