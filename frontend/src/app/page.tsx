export const metadata = {
  title: "IMDA Policy Analytics",
  description: "Agentic Policy Data Analytics Platform",
};

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          IMDA GenAI Demo
        </h1>
        <p className="text-2xl text-gray-700 mb-8">
          Bootstrap OK ✓
        </p>
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md mx-auto">
          <p className="text-gray-600 mb-4">
            Agentic Policy Data Analytics Platform
          </p>
          <p className="text-sm text-gray-500">
            Version 0.1.0 — Local Development
          </p>
        </div>
      </div>
    </main>
  );
}
