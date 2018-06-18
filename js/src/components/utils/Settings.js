import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {ButtonGroup, Button} from 'reactstrap'
import {as_title} from '../../utils'
import {Loading} from './Errors'

export const render_bool = v => (
  <FontAwesomeIcon icon={v ? 'check' : 'times'} />
)

const Buttons = ({buttons, className}) => (
  buttons && <div className="text-right mb-2">
    <ButtonGroup>
      {buttons.map(b => (
        <Button key={b.name} tag={Link} to={b.link}>{b.name}</Button>
      ))}
    </ButtonGroup>
  </div>
)

export class RenderItem extends React.Component {
  constructor (props) {
    super(props)
    this.requests = this.props.requests
    this.render_key = this.render_key.bind(this)
    this.render_value = this.render_value.bind(this)
    this.update = this.update.bind(this)
    this.got_data = this.got_data.bind(this)
    this.get_uri = this.get_uri.bind(this)
    this.formats = {}
  }

  get_uri () {
    return `/${this.props.page.name}/`
  }

  componentDidMount () {
    this.props.setRootState({
      page_title: as_title(this.props.page.name),
    })
    this.update()
  }

  async update () {
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

  extra () {}

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
}

export class RenderList extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      items: null,
      count: null,
      buttons: null,
    }
  }

  render () {
    if (!this.state.items) {
      return <Loading/>
    }
    const keys = Object.keys(this.state.items[0])
    keys.splice(keys.indexOf('id'), 1)
    return [
      <Buttons key={1} buttons={this.state.buttons}/>,
      <table key={2} className="table">
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
      </table>,
      <div key={3}>
        {this.extra()}
      </div>
    ]
  }
}

export class RenderDetails extends RenderItem {
  constructor (props) {
    super(props)
    this.state = {
      item: null,
      buttons: []
    }
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

  render () {
    if (!this.state.item) {
      return <Loading/>
    }
    const keys = Object.keys(this.state.item)
    for (let key of this.skip_keys) {
      keys.splice(keys.indexOf(key), 1)
    }
    keys.splice(keys.indexOf('_response_status'), 1)
    return [
      <Buttons key={1} buttons={this.state.buttons}/>,
      <div key={2} className="mb-4">
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
      </div>,
      <div key={3}>
        {this.extra()}
      </div>,
    ]
  }
}

export const ImageThumbnail = ({image, alt}) => (
  image ? <img src={image + '/thumb.jpg'} alt={alt} className="img-thumbnail"/> : <span>&mdash;</span>
)
