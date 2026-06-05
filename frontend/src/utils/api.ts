'use client';

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
    let token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    
    // Set headers
    const headers = new Headers(options.headers || {});
    if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    // Add ngrok bypass header by default
    if (!headers.has('ngrok-skip-browser-warning')) {
        headers.set('ngrok-skip-browser-warning', 'true');
    }
    
    options.headers = headers;

    let res = await fetch(url, options);

    // If 401 Unauthorized, try refreshing the token
    if (res.status === 401) {
        const refreshToken = typeof window !== 'undefined' ? localStorage.getItem('refreshToken') : null;
        if (refreshToken) {
            try {
                const refreshRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'ngrok-skip-browser-warning': 'true'
                    },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });

                if (refreshRes.ok) {
                    const data = await refreshRes.json();
                    localStorage.setItem('token', data.access_token);
                    localStorage.setItem('refreshToken', data.refresh_token);

                    // Retry original request with new token
                    const newHeaders = new Headers(options.headers);
                    newHeaders.set('Authorization', `Bearer ${data.access_token}`);
                    options.headers = newHeaders;

                    res = await fetch(url, options);
                } else {
                    // Refresh failed, clean up and redirect to login
                    localStorage.removeItem('token');
                    localStorage.removeItem('refreshToken');
                    window.location.href = '/login';
                }
            } catch (err) {
                localStorage.removeItem('token');
                localStorage.removeItem('refreshToken');
                window.location.href = '/login';
            }
        } else {
            // No refresh token available, redirect to login
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
    }

    return res;
}
