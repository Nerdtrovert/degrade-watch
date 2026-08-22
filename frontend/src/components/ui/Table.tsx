// src/components/ui/Table.tsx
import React from 'react';

type TableProps = {
  columns: { header: string; accessor: string }[];
  data: Record<string, any>[];
  className?: string;
};

export const Table: React.FC<TableProps> = ({ columns, data, className = '' }) => {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="min-w-full border border-border text-sm">
        <thead className="bg-gray-100">
          <tr>
            {columns.map(col => (
              <th
                key={col.accessor}
                className="px-4 py-2 text-left font-medium text-text-primary border-b border-border"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="odd:bg-surface even:bg-gray-50 hover:bg-gray-100">
              {columns.map(col => (
                <td key={col.accessor} className="px-4 py-2 border-b border-border text-text-secondary">
                  {row[col.accessor]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
