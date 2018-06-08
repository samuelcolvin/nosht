import React, {Component} from 'react'
import {Link} from 'react-router-dom'
import {Loading} from '../utils/Errors'


class SettingsList extends Component {
  constructor (props) {
    super(props)
    this.requests = this.props.requests
    this.state = {
      items: null,
      count: null,
    }
    this.url = null
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
            {keys.map((name, i) => (
              <th key={i} scope="col">{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {this.state.items.map((item, i) => (
            <tr key={i}>
              {keys.map((key, j) => (
                j === 0 ? (
                  <td key={j}>
                    <Link to={`${item.id}/`}>{item[key]}</Link>
                  </td>
                ) : (
                  <td key={j}>{item[key]}</td>
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
