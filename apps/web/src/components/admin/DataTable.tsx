import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DataTableProps {
  headers: string[];
  children: ReactNode;
  className?: string;
}

export function DataTable({ headers, children, className }: DataTableProps) {
  return (
    <div className={cn("overflow-hidden rounded-lg border bg-card", className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40">
              {headers.map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">{children}</tbody>
        </table>
      </div>
    </div>
  );
}

export function TableRow({ children, onClick, className }: { children: ReactNode; onClick?: () => void; className?: string }) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors hover:bg-muted/30",
        onClick && "cursor-pointer",
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TableCell({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn("px-4 py-3 align-middle", className)}>{children}</td>;
}
