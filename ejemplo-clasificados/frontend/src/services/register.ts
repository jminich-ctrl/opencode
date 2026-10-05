/**
 * Registra un usuario enviando sus credenciales al backend.
 * @param email - El correo electrónico del usuario
 * @param password - La contraseña del usuario
 * @throws {Error} Si ocurre un error durante el registro
 */
export async function registrarUsuario(email: string, password: string): Promise<void> {
  const response = await fetch('http://localhost:8000/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Error al registrar usuario');
  }
}