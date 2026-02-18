
import React, { useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  flexRender,
  ColumnDef,
  SortingState
} from '@tanstack/react-table';
import { Database, Search, ArrowUpDown, AlertCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { DatabaseTables } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

// --- TABLE COMPONENT ---
const FilterableTable = ({ title, data, columns }: { title: string, data: any[], columns: ColumnDef<any>[] }) => {
  const [globalFilter, setGlobalFilter] = useState('');
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    state: {
      globalFilter,
      sorting,
    },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
  });

  return (
    <Card className="overflow-hidden border-border bg-card/40 backdrop-blur-sm">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-medium capitalize flex items-center gap-2">
            {title}
            <Badge variant="secondary" className="text-xs font-normal">{data.length} records</Badge>
          </CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              placeholder="Search data..."
              value={globalFilter ?? ''}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 pl-8 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-border">
          <div className="overflow-x-auto">
            <table className="w-full caption-bottom text-sm text-left">
              <thead className="[&_tr]:border-b [&_tr]:border-border">
                <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                  {table.getHeaderGroups().map((headerGroup) => (
                    headerGroup.headers.map((header) => (
                      <th key={header.id} className="h-10 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0">
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))
                  ))}
                </tr>
              </thead>
              <tbody className="[&_tr:last-child]:border-0">
                {table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="border-b border-border transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="p-4 align-middle [&:has([role=checkbox])]:pr-0">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={columns.length} className="h-24 text-center">
                      No results.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// --- MAIN COMPONENT ---
const DataViewer: React.FC = () => {
  const { data: dbData, isLoading, error } = useQuery({
    queryKey: ['database-preview'],
    queryFn: () => api.get<DatabaseTables>('/database/preview')
  });

  if (isLoading) return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 w-48 bg-muted rounded" />
      <div className="h-64 bg-muted/50 rounded-xl" />
      <div className="h-64 bg-muted/50 rounded-xl" />
    </div>
  );

  if (error) return (
    <div className="p-6 bg-destructive/10 text-destructive border border-destructive/20 rounded-xl flex items-center gap-3">
      <AlertCircle className="w-6 h-6" />
      <div>
        <h3 className="font-semibold">Failed to load data</h3>
        <p className="text-sm opacity-80">{(error as any).message}</p>
      </div>
    </div>
  );

  if (!dbData) return null;

  // Generate columns dynamically (simplified for speed)
  const generateColumns = (data: any[]): ColumnDef<any>[] => {
    if (!data.length) return [];
    return Object.keys(data[0]).map(key => ({
      accessorKey: key,
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="-ml-4 h-8 data-[state=open]:bg-accent"
          >
            {key.replace(/_/g, ' ')}
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
    }));
  };

  return (
    <div className="space-y-8 pb-12">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-primary/10 rounded-lg">
          <Database className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Forensic Data Lake</h2>
          <p className="text-muted-foreground">Live view of simulated company records.</p>
        </div>
      </div>

      <FilterableTable
        title="Expenses"
        data={dbData.expenses}
        columns={generateColumns(dbData.expenses)}
      />
      <FilterableTable
        title="Employees"
        data={dbData.employees}
        columns={generateColumns(dbData.employees)}
      />
      <FilterableTable
        title="Contracts"
        data={dbData.contracts}
        columns={generateColumns(dbData.contracts)}
      />
    </div>
  );
};

export default DataViewer;

