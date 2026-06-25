export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center text-sm text-red-800">
      <p className="font-medium">Failed to load data</p>
      <p className="mt-1">{message}</p>
      <p className="mt-2 text-xs">Make sure the API is running: cd apps/api && uvicorn app.main:app --reload</p>
    </div>
  );
}
