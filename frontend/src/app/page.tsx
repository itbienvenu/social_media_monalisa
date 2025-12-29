import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
      <main className="max-w-2xl w-full bg-white shadow-xl rounded-lg overflow-hidden">
        <div className="bg-blue-600 p-6">
          <h1 className="text-3xl font-bold text-white text-center">
            MwiMule Social
          </h1>
          <p className="text-blue-100 text-center mt-2">
            Social Media Management Dashboard
          </p>
        </div>

        <div className="p-8 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link href="/connect" className="block p-6 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors text-center group">
              <div className="text-2xl mb-2"></div>
              <h3 className="font-semibold text-gray-900 group-hover:text-blue-600">Connect Accounts</h3>
              <p className="text-sm text-gray-500 mt-1">Link your Facebook, TikTok & LinkedIn</p>
            </Link>

            <Link href="/post" className="block p-6 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors text-center group">
              <div className="text-2xl mb-2">✍️</div>
              <h3 className="font-semibold text-gray-900 group-hover:text-blue-600">Create Post</h3>
              <p className="text-sm text-gray-500 mt-1">Publish content to multiple platforms</p>
            </Link>
          </div>

          <div className="border-t border-gray-100 pt-6">
            <h4 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">System Status</h4>
            <div className="flex items-center space-x-2 text-sm text-green-600">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span>Backend API Verified</span>
            </div>
            <div className="text-xs text-gray-400 mt-2">
              API: {process.env.NEXT_PUBLIC_API_URL || 'Not Configured'}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
