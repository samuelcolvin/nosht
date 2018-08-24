import React from 'react'
import {Link} from 'react-router-dom'
import {Card, CardImg, CardTitle, CardText, CardBody, Row, Col} from 'reactstrap'
import {chunk_array, image_thumb} from './utils'
import WithContext from './utils/context'
import EventCards from './events/Cards'


const Category = ({cat}) => {
  return (
    <Col md="4" className="box-container">
      <Link className="index-card" to={`/${cat.slug}/`}>
        <Card>
          <CardImg top width="100%" src={image_thumb(cat.image)} alt={cat.name}/>
          <CardBody>
            <CardTitle>{cat.name}</CardTitle>
            <CardText>
              {cat.description}
            </CardText>
          </CardBody>
        </Card>
      </Link>
    </Col>
  )
}

class Index extends React.Component {
  componentDidMount () {
    this.props.ctx.setRootState({
      page_title: null,
      background: null,
      extra_menu: null,
      active_page: null,
    })
  }

  render () {
    const categories = this.props.ctx.company.categories
    const events = this.props.ctx.company.highlight_events
    return (
      <div className="card-grid">
        {events.length ?
          <div>
            <h1>Highlighted Events</h1>
            <EventCards events={events}/>
          </div>
          :
          null
        }
        <div className="mt-4">
          <h1>Categories</h1>
          {chunk_array(categories, 3).map((chunk, i) => (
            <Row key={i}>
              {chunk.map((cat, j) => <Category cat={cat} key={j}/>)}
            </Row>
          ))}
          {categories.length === 0 && <span className="text-muted">No Categories Live</span>}
        </div>
      </div>
    )
  }
}
export default WithContext(Index)
