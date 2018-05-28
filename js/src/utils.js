export const load_script = url => {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = url
    script.onload = () => resolve()
    script.onreadystatechange = () => resolve()
    script.onerror = () => reject()
    document.body.appendChild(script)
  })
}

export const make_url = path => {
  return window.location.origin + '/api/' + path
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
    const on_error = msg => {
      console.error('request error', msg, url, xhr)
      reject(msg)
    }
    xhr.open(method, url)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.onload = () => {
      if (config.expected_statuses.includes(xhr.status)) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch (error) {
          on_error(`error decoding json: ${error}`)
        }
      } else {
        on_error(`wrong response code ${xhr.status}, Response: ${xhr.responseText.substr(0, 500)}`)
      }
    }
    xhr.onerror = () => {
      on_error(`Error requesting data ${xhr.statusText}: ${xhr.status}`)
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
