import * as XLSX from 'xlsx';
import fs from 'fs';

export async function writeExcelSheet<T>(filePath: string, sheetName: string, data: T[]): Promise<void> {
    let workbook: XLSX.WorkBook;

    if (fs.existsSync(filePath)) {
        const buffer = fs.readFileSync(filePath);
        workbook = XLSX.read(buffer, { type: 'buffer', cellDates: true });
    } else {
        workbook = XLSX.utils.book_new();
    }

    const worksheet = XLSX.utils.json_to_sheet(data);

    // If sheet exists, replace it
    if (workbook.SheetNames.includes(sheetName)) {
        workbook.Sheets[sheetName] = worksheet;
    } else {
        XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
    }

    const outputBuffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
    fs.writeFileSync(filePath, outputBuffer);
}
