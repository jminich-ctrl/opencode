export async function login(username: string, password: string): Promise<void> {
  const response = await fetch('/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username,
      password
    })
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || 'Error al iniciar sesión');
  }

  // Guardar la cookie de sesión
  const setCookieHeader = response.headers.get('set-cookie');
  if (setCookieHeader) {
    document.cookie = setCookieHeader;
  }
}