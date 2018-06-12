import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col, ButtonGroup, Button, Modal, ModalHeader, ModalBody, ModalFooter} from 'reactstrap'
import {as_title} from '../../utils'
import {Loading} from './Errors'

export const render_bool = v => (
  <FontAwesomeIcon icon={v ? 'check' : 'times'} />
)

export class RenderItem extends React.Component {
  constructor (props) {
    super(props)
    this.requests = this.props.requests
    this.render_key = this.render_key.bind(this)
    this.render_value = this.render_value.bind(this)
    this.got_data = this.got_data.bind(this)
    this.render_loaded = this.render_loaded.bind(this)
    this.get_uri = this.get_uri.bind(this)
    this.formats = {}
  }

  get_uri () {
    return `/${this.props.page.name}/`
  }

  async componentDidMount () {
    this.props.setRootState({
      page_title: as_title(this.props.page.name),
    })
    let data = null
    const uri = this.get_uri()
    try {
      data = await this.requests.get(uri)
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.got_data(data)
  }

  async got_data (data) {
    this.setState(data)
  }

  render_key (key) {
    const fmt = this.formats[key]
    if (fmt && fmt.title) {
      return fmt.title
    }
    return as_title(key)
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

  render_loaded () {
    return <div>todo</div>
  }

  render () {
    if (this.state.item || this.state.items) {
      return this.render_loaded()
    } else {
      return <Loading/>
    }
  }
}

export class RenderList extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      items: null,
      count: null,
    }
  }

  render_loaded () {
    const keys = Object.keys(this.state.items[0])
    keys.splice(keys.indexOf('id'), 1)
    return (
      <table className="table">
        <thead>
          <tr>
            {keys.map((key, i) => (
              <th key={i} scope="col">{this.render_key(key)}</th>
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

export class RenderDetails extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      item: null,
      buttons: []
    }
    this.extra = this.extra.bind(this)
    this.id = this.props.match.params.id
    this.skip_keys = ['id']
  }

  get_uri () {
    return `/${this.props.page.name}/${this.id}/`
  }

  async got_data (data) {
    this.setState({item: data})
    this.props.setRootState({
      page_title: data.name || as_title(this.props.page.name),
    })
  }

  extra () {}

  render_loaded () {
    const keys = Object.keys(this.state.item)
    for (let key of this.skip_keys) {
      keys.splice(keys.indexOf(key), 1)
    }
    return [
      <Row key={1}>
        <Col md={8}>
          {keys.map((key, i) => (
            <div key={key} className="item-detail">
              <div className="key">
                {this.render_key(key)}
              </div>
              <div className="value">
                {this.render_value(this.state.item, key)}
              </div>
            </div>
          ))}
        </Col>
          {this.state.buttons && (
            <Col md={4} className="text-right">
              <ButtonGroup vertical={true}>
                {this.state.buttons.map(b => (
                  <Button key={b.name} tag={Link} to={b.link}>{b.name}</Button>
                ))}
              </ButtonGroup>
            </Col>
          )}
      </Row>,
      <div key={2}>
        {this.extra()}
      </div>,
    ]
  }
}
