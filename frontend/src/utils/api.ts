'use client';

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
    // Set headers - cookies are sent automatically by browser for HttpOnly cookies
    const headers = new Headers(options.headers || {});
    // Add ngrok bypass header by default
    if (!headers.has('ngrok-skip-browser-warning')) {
        headers.set('ngrok-skip-browser-warning', 'true');
    }
    
    options.headers = headers;
    // Important: include credentials for cookie support
    options.credentials = 'include';

    let res = await fetch(url, options);

    if (res.status === 401) {
        try {
            const refreshRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                credentials: 'include',
                body: JSON.stringify({ refresh_token: 'dummy' })
            });

            if (refreshRes.ok) {
                res = await fetch(url, options);
            } else {
                window.location.href = '/login';
            }
        } catch (err) {
            window.location.href = '/login';
        }
    }

    return res;
}
