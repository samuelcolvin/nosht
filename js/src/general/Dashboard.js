import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {ButtonGroup, Button} from 'reactstrap'
import requests from '../utils/requests'
import {as_title} from '../utils'
import {Loading} from './Errors'
import Map from './Map'
import ButtonConfirm from './Confirm'

export const render = v => {
  if (typeof v === 'boolean') {
    return <FontAwesomeIcon icon={v ? 'check' : 'times'}/>
  } else if ([null, undefined].includes(v)) {
    return <Dash/>
  } else if (typeof v === 'object') {
    if (Object.keys(v).includes('$$typeof')) {
      return v
    } else {
      return JSON.stringify(v)
    }
  } else {
    return v
  }
}

const Buttons = ({buttons, ctx}) => (
  buttons && <div className="text-right mb-2">
    <ButtonGroup className="btn-divider">
      {buttons.filter(b => b).map(b => (
        b.confirm_msg ?
          <ButtonConfirm key={b.name}
                         action={b.action}
                         modal_title={b.name}
                         btn_text={b.name}
                         redirect_to={b.redirect_to}
                         success_msg={b.success_msg}
                         done={b.done}
                         btn_size="sm"
                         className="ml-2">
            {b.confirm_msg}
          </ButtonConfirm>
          :
          <Button key={b.name} tag={Link} to={b.link} disabled={b.disabled || false}>{b.name}</Button>
      ))}
    </ButtonGroup>
  </div>
)

export const Dash = () => <span>&mdash;</span>

export const Detail = ({name, wide, edit_link, children}) => (
  <div className={`item-detail${wide ? ' wide' : ''}`}>
    <div className="key">
      {name}
      {edit_link && <Button tag={Link} to={edit_link} size="sm" className="ml-2">
        <FontAwesomeIcon icon="pen" className="mr-1"/>
        Edit {name}
      </Button>}
    </div>
    <div className="value">
      {render(children)}
    </div>
  </div>
)

export class RenderItem extends React.Component {
  constructor (props) {
    super(props)
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
    this.props.ctx.setRootState({
      page_title: as_title(this.props.page.name),
    })
    this.update()
  }

  async update () {
    let data = null
    const uri = this.get_uri()
    try {
      data = await requests.get(uri)
    } catch (error) {
      this.props.ctx.setError(error)
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
    } else {
      return render(v)
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

  get_link (item) {
    return `${item.id}/`
  }

  render () {
    if (!this.state.items) {
      return <Loading/>
    } else if (this.state.items.length === 0) {
      return [
        <Buttons key="1" buttons={this.state.buttons}/>,
        <div key="2" className="text-muted text-center h5 mt-4">
          No {as_title(this.props.page.name)} found
        </div>
      ]
    }
    const keys = Object.keys(this.state.items[0])
    keys.includes('id') && keys.splice(keys.indexOf('id'), 1)
    return [
      <Buttons key="1" buttons={this.state.buttons}/>,
      <table key="2" className="table">
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
                    <Link to={this.get_link(item)}>{this.render_value(item, key)}</Link>
                  </td>
                ) : (
                  <td key={j}>{this.render_value(item, key)}</td>
                )
              ))}
            </tr>
          ))}
        </tbody>
      </table>,
      <div key="3">
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
    this.pre = this.pre.bind(this)
  }

  get_uri () {
    return `/${this.props.page.name}/${this.id}/`
  }

  async got_data (data) {
    this.setState({item: data})
    this.props.ctx.setRootState({
      page_title: data.name || as_title(this.props.page.name),
    })
  }

  pre () {}

  render () {
    if (!this.state.item) {
      return <Loading/>
    }
    const keys = (
      Object.keys(this.state.item)
      .filter(k => !['id', '_response_status', 'name'].includes(k) && this.formats[k] !== null)
      .sort((a, b) => ((this.formats[a] || {}).wide || 0) - ((this.formats[b] || {}).wide || 0))
      .sort((a, b) => ((this.formats[a] || {}).index || 0) - ((this.formats[b] || {}).index || 0))
    )
    const pre = this.pre()
    return [
      <Buttons key="b" buttons={this.state.buttons}/>,
      this.state.item.name && <h1 key="t">{this.state.item.name}</h1>,
      pre ? <div key="p">{pre}</div> : null,
      <div key="d" className="mb-4">
        {keys.map(key => (
          <Detail key={key}
                  name={this.render_key(key)}
                  wide={Boolean((this.formats[key] || {}).wide)}
                  edit_link={(this.formats[key] || {}).edit_link}>
            {this.render_value(this.state.item, key)}
          </Detail>
        ))}
      </div>,
      <div key="e">
        {this.extra()}
      </div>,
    ]
  }
}

export const ImageThumbnail = ({image, alt, image_type}) => (
  image ?
    <img src={image + `/${image_type || 'thumb'}.jpg`} alt={alt} className="img-thumbnail"/>
    :
    <span>&mdash;</span>
)

export const MiniMap = ({lat, lng, name}) => (
  <div>
    {name}
    <Map geolocation={{lat, lng, name}} height={200} width={400} className="rounded"/>
  </div>
)
