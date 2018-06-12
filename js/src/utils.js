import format from 'date-fns/format'

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
      // script.onreadystatechange = () => resolve()
    }
  })
}

export const load_script_callback = url => {
  return new Promise((resolve, reject) => {
    url = url.replace('<callback-function>', '_load_script_complete')
    if (document.querySelector(`script[src="${url}"`)) {
      // script already loaded, but wait to resolve to make sure the callback has been called
      setTimeout(() => resolve(), 100)
    } else {
      window._load_script_complete = () => resolve()
      _add_script(url, reject)
    }
  })
}

export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

export const make_url = path => {
  if (path.match(/^https?:\//)) {
    return path
  } else {
  return window.location.origin + '/api/' + path.replace(/^\//, '')
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
    xhr.onload = () => {
      if (config.expected_statuses.includes(xhr.status)) {
        try {
          const data = JSON.parse(xhr.responseText)
          if (typeof data === 'object') {
            data.response_status = xhr.status
          }
          resolve(data)
        } catch (error) {
          on_error('Error decoding json', error)
        }
      } else {
        let response_data
        try {
          response_data = JSON.parse(xhr.responseText)
          if (response_data.message) {
            on_error(xhr.status === 401 ?
              response_data.message : `Unexpected response ${xhr.status}: ${response_data.message}`
            )
            return
          }
        } catch (e) {
          // ignore and use normal error
        }
        on_error(`Unexpected response ${xhr.status}`, response_data)
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

export const put = (path, data, config) => {
  config = config || {}
  config.send_data = data
  return request('PUT', path, config)
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

export const as_title = s => s.replace(/(_|\b)\w/g, l => l.toUpperCase().replace('_', ' '))
