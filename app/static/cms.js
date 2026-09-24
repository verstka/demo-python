document.querySelectorAll('[data-dialog-open]').forEach((trigger) => {
  trigger.addEventListener('click', () => {
    const dialog = document.getElementById(trigger.dataset.dialogOpen)
    if (dialog instanceof HTMLDialogElement) dialog.showModal()
  })
})

document.querySelectorAll('[data-dialog-close]').forEach((trigger) => {
  trigger.addEventListener('click', () => {
    const dialog = trigger.closest('dialog')
    if (dialog instanceof HTMLDialogElement) dialog.close()
  })
})

document.querySelectorAll('dialog').forEach((dialog) => {
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close()
  })
})

document.addEventListener('click', (event) => {
  document.querySelectorAll('.action-menu[open]').forEach((menu) => {
    if (!menu.contains(event.target)) menu.removeAttribute('open')
  })
})

const authForm = document.querySelector('[data-auth-form]')
if (authForm) {
  authForm.addEventListener('submit', () => {
    const button = authForm.querySelector('[type="submit"]')
    if (button) button.setAttribute('aria-busy', 'true')
  })
}

const countFormatter = new Intl.NumberFormat('en-US')
const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
const countStartDelay = 0

const formatCountValue = (value, format) => {
  if (format === 'comma') return countFormatter.format(value)
  return String(value)
}

document.querySelectorAll('[data-count-target]').forEach((counter) => {
  const target = Number.parseInt(counter.dataset.countTarget || '0', 10)
  if (!Number.isFinite(target) || target <= 0) return

  const duration = 2000
  const format = counter.dataset.countFormat
  const setValue = (value) => {
    counter.textContent = formatCountValue(value, format)
  }

  if (reducedMotion || typeof window.requestAnimationFrame !== 'function') {
    setValue(target)
    return
  }

  const startCounter = () => {
    const startedAt = performance.now()
    const tick = (now) => {
      const progress = Math.min((now - startedAt) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(target * eased))

      if (progress < 1) window.requestAnimationFrame(tick)
    }

    window.requestAnimationFrame(tick)
  }

  window.setTimeout(startCounter, countStartDelay)
})
