import { test, expect } from '@playwright/test'

test('la puerta de entrada muestra el asiento y el formulario de acceso', async ({ page }) => {
  await page.goto('/login')

  await expect(page.locator('h1')).toContainText('contabilidad')
  await expect(page.getByLabel('Email')).toBeVisible()
  await expect(page.locator('#contrasena')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ingresar' })).toBeVisible()
})

test('el asiento de ejemplo cierra balanceado', async ({ page }) => {
  await page.goto('/login')

  await expect(page.getByText('Asiento balanceado · debe = haber')).toBeVisible({
    timeout: 5000,
  })
})

test('una ruta protegida redirige al login', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL(/\/login$/)
})
