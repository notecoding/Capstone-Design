// src/components/common/Loading.jsx
export default function Loading() {
  return (
    <div className="flex items-center justify-center w-full py-16">
      <div className="w-8 h-8 rounded-full animate-spin"
           style={{ border: "3px solid var(--border)", borderTopColor: "var(--brand)" }} />
    </div>
  );
}