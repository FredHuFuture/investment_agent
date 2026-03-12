export default function ErrorAlert({ message }: { message: string }) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl p-4 text-sm">
      {message}
    </div>
  );
}
