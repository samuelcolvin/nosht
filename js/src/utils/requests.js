const make_url = path => {
  if (path.match(/^https?:\//)) {
    return path
  } else {
    const origin = process.env.REACT_APP_REQUEST_ORIGIN || window.location.origin
    return origin + path.replace(/^(\/)?/, '/api/')
  }
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

const request = (method, path, config) => {
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
    const on_error = (msg, error_details) => reject({msg, url, xhr, error_details, status: xhr.status})
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

export default {
  get: (path, args, config) => request('GET', path, {args, ...config}),
  post: (path, send_data, config) => request('POST', path, {send_data, ...config}),
}
