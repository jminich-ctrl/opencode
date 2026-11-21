    # Manejador para RequestValidationError (validación de datos)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Devolvemos un error 400 con el formato esperado
        # Extract the first error message from the validation errors
        error_messages = [str(error) for error in exc.errors()]
        first_error = error_messages[0] if error_messages else "Datos de entrada inválidos"
        return JSONResponse(
            status_code=400,
            content={"error": first_error}
        )

    # Manejador para HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Conservamos el código de estado y reescribimos el cuerpo
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )