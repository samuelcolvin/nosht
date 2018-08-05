import format from 'date-fns/format'

export const unique = (value, index, array) => array.indexOf(value) === index

export const currency_lookup = {
  gbp: '£',
  usd: '$',
  eur: '€',
}

export const format_money = (currency, money) => (
  currency_lookup[currency] + (money || 0).toFixed(2)
)

export const format_money_free = (currency, money) => (
  money ? format_money(currency, money) : 'Free'
)

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

export const error_response = xhr => {
  let response_data = {}
  try {
    response_data = JSON.parse(xhr.responseText)
  } catch (e) {
    // ignore and use normal error
  }
  response_data.message = response_data.message || `Unexpected response ${xhr.status}`
  return response_data
}

export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export const make_url = path => {
  if (path.match(/^https?:\//)) {
    return path
  } else {
    return window.location.origin + path.replace(/^(\/)?/, '/api/')
  }
}

export const request = (method, path, config) => {
  let url = make_url(path)

  config = config || {}
  if (config.args) {
    const arg_list = []
    const add_arg = (n, v) => arg_list.push(encodeURIComponent(n) + '=' + encodeURIComponent(v))
    for (let [name, value] of Object.entries(config.args)) {
      if (Array.isArray(value)) {
        for (let value_ of value) {
          add_arg(name, value_)
        }
      } else if (value !== null && value !== undefined) {
        add_arg(name, value)
      }
    }
    if (arg_list.length > 0) {
      url += '?' + arg_list.join('&')
    }
  }

  if (Number.isInteger(config.expected_statuses)) {
    config.expected_statuses = [config.expected_statuses]
  } else {
    config.expected_statuses = config.expected_statuses || [200]
  }
  if (config.send_data) {
    config.send_data = JSON.stringify(config.send_data)
  }
  // await sleep(2000)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const on_error = (user_msg, error_details) => reject({user_msg, url, xhr, error_details, status: xhr.status})
    xhr.open(method, url)
    xhr.setRequestHeader('Accept', 'application/json')
    method !== 'GET' && xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.onload = () => {
      if (config.expected_statuses.includes(xhr.status)) {
        try {
          const data = JSON.parse(xhr.responseText)
          if (typeof data === 'object') {
            data._response_status = xhr.status
          }
          resolve(data)
        } catch (error) {
          on_error('Error decoding json', error)
        }
      } else {
        const response_data = error_response(xhr)
        on_error(response_data.message, response_data)
      }
    }
    xhr.onerror = error => {
      on_error('Unable to connect to the server, check your internet connection', error)
    }
    xhr.send(config.send_data || null)
  })
}

export const get = (path, args, config) => {
  config = config || {}
  config.args = args
  return request('GET', path, config)
}

export const post = (path, data, config) => {
  config = config || {}
  config.send_data = data
  return request('POST', path, config)
}

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

export const as_title = s => s.replace(/(_|\b)\w/g, l => l.toUpperCase().replace('_', ' ')).replace('-', ' ')

export const get_component_name = WrappedComponent => (
  WrappedComponent.displayName || WrappedComponent.name || 'Component'
)

export const user_full_name = user => `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email
