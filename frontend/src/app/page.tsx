export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="text-center space-y-6 p-8">
        <h1 className="text-5xl font-bold text-gray-900">
          IMDA GenAI Demo
        </h1>
        <p className="text-2xl text-gray-700">
          Policy Data Analytics Platform
        </p>
        <div className="mt-8 p-4 bg-green-100 border-2 border-green-500 rounded-lg inline-block">
          <p className="text-xl font-semibold text-green-800">
            ✓ Bootstrap OK
          </p>
        </div>
        <div className="mt-6 text-sm text-gray-600">
          <p>Backend API: <code className="bg-gray-200 px-2 py-1 rounded">http://localhost:8000</code></p>
          <p className="mt-2">Frontend: <code className="bg-gray-200 px-2 py-1 rounded">http://localhost:3000</code></p>
        </div>
      </div>
    </main>
  )
}
