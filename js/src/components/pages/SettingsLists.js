import React, {Component} from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {as_title, format_event_start, format_event_duration} from '../../utils'
import {Loading} from '../utils/Errors'

const render_bool = v => (
  <FontAwesomeIcon icon={v ? 'check' : 'times'} />
)

class SettingsList extends Component {
  constructor (props) {
    super(props)
    this.requests = this.props.requests
    this.render_value = this.render_value.bind(this)
    this.state = {
      items: null,
      count: null,
    }
    this.url = null
    this.formats = {}
  }

  async componentDidMount () {
    this.props.setRootState({
      page_title: 'foobar',
    })
    try {
      const data = await this.requests.get(this.url)
      this.setState(data)
    } catch (error) {
      this.props.setRootState({error})
    }
  }

  render_value (item, key) {
    const fmt = this.formats[key]
    const v = item[key]
    if (fmt && fmt.render) {
      return fmt.render(v, item)
    } else if (typeof v === 'boolean') {
      return render_bool(v)
    } else {
      return v
    }
  }

  render () {
    if (!this.state.items) {
      return <Loading/>
    }
    const keys = Object.keys(this.state.items[0])
    keys.splice(keys.indexOf('id'), 1)
    return (
      <table className="table">
        <thead>
          <tr>
            {keys.map((key, i) => (
              <th key={i} scope="col">{(this.formats[key] || {}).title || as_title(key)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {this.state.items.map((item, i) => (
            <tr key={i}>
              {keys.map((key, j) => (
                j === 0 ? (
                  <td key={j}>
                    <Link to={`${item.id}/`}>{this.render_value(item, key)}</Link>
                  </td>
                ) : (
                  <td key={j}>{this.render_value(item, key)}</td>
                )
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    )
  }
}

export class EventsList extends SettingsList {
  constructor (props) {
    super(props)
    this.url = '/events/'
    this.formats = {
      start_ts: {
        title: 'Date',
        render: (v, item) => format_event_start(v, item.duration),
      },
      duration: {
        render: format_event_duration
      }
    }
  }
}

export class CategoriesList extends SettingsList {
  constructor (props) {
    super(props)
    this.url = '/categories/'
  }
}


export class UsersList extends SettingsList {
  constructor (props) {
    super(props)
    this.url = '/users/'
  }
}
