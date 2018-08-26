import format from 'date-fns/format'

export const unique = (value, index, array) => array.indexOf(value) === index

export const grecaptcha_execute = action => window.grecaptcha.execute(0, {action})

const _add_script = (url, reject) => {
  const script = document.createElement('script')
  script.src = url
  script.onerror = e => reject(e)
  document.body.appendChild(script)
  setTimeout(() => reject(`script "${url}" timed out`), 8000)
  return script
}

export const load_script = url => {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${url}"`)) {
      // script already loaded
      resolve()
    } else {
      const script = _add_script(url, reject)
      script.onload = () => resolve()
    }
  })
}

export const load_script_callback = url => {
  const callback_name = '_load_script_complete_' + btoa(url).substr(0, 10)
  return new Promise((resolve, reject) => {
    url = url.replace('<callback-function>', callback_name)
    if (document.querySelector(`script[src="${url}"]`)) {
      // script already loaded, but wait to resolve to make sure the callback has been called
      setTimeout(() => resolve(), 100)
    } else {
      window[callback_name] = () => resolve()
      _add_script(url, reject)
    }
  })
}

export const window_property = prop_name => {
  return new Promise((resolve, reject) => {
    const prop = window[prop_name]
    if (prop) {
      resolve(prop)
      return
    }
    const clear_interval = setInterval(() => {
      const prop = window[prop_name]
      if (prop) {
        clearInterval(clear_interval)
        resolve(prop)
      }
    }, 50)

    setTimeout(() => {
      clearInterval(clear_interval)
      reject(`timeout getting window.${prop_name}`)
    }, 5000)
  })
}

export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

const DF = 'Do MMM'
const DFY = 'Do MMM YYYY'
const DTF = 'Do MMM, h:mma'

export const format_date = (ts, y) => format(new Date(ts), y ? DFY : DF)
export const format_datetime = ts => format(new Date(ts), DTF)

export const format_event_start = (ts, duration) => duration === null ? format_date(ts) : format_datetime(ts)
export const format_event_duration = duration => duration === null ? 'All day' : format_duration(duration)

export const format_duration = seconds => {
  let minutes = Math.round(seconds / 60)
  if (minutes === 60) {
    return '1 hour'
  }
  if (minutes < 60) {
    return `${minutes} mins`
  }
  const hours = Math.floor(minutes / 60)
  minutes = minutes % 60
  if (hours === 1) {
    return `1 hour ${minutes} mins`
  }
  if (minutes === 0) {
    return `${hours} hours`
  } else {
    return `${hours} hours ${minutes} mins`
  }
}

export const chunk_array = (array, size) => {
  const a2 = array.slice()
  const results = []
  while (a2.length) {
    results.push(a2.splice(0, size))
  }
  return results
}

export const as_title = s => s.replace(/(_|-)/g, ' ').replace(/(_|\b)\w/g, l => l.toUpperCase())

export const get_component_name = WrappedComponent => (
  WrappedComponent.displayName || WrappedComponent.name || 'Component'
)

export const user_full_name = user => `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email

export const on_mobile = /mobile|ip(hone|od|ad)|android|blackberry|opera mini|iemobile/i.test(navigator.userAgent)

export const set_tmp_name = (first_name, last_name) => {
  window.sessionStorage['user_name'] = JSON.stringify({first_name, last_name})
}

export const get_tmp_name = () => {
  const v = window.sessionStorage[`user_name`]
  return v ? JSON.parse(v) : {first_name: null, last_name: null}
}

export const image_thumb = (img, rep) => img && img.replace(/main\.(\w+)$/, (rep || 'thumb') + '.$1')


export const watch_scroll = callback => {
  if (on_mobile) {
    // don't do this on mobile
    return
  }
  let y_pos = window.scrollY
  let busy = false
  window.addEventListener('scroll', () => {
    y_pos = window.scrollY
    if (!busy) {
      window.requestAnimationFrame(() => {
        callback(y_pos)
        busy = false
      })
      busy = true
    }
  })
}
