#if !defined(__QCUSTOMPLOT_SIP_DATACONTAINER_H)
#define __QCUSTOMPLOT_SIP_DATACONTAINER_H

#include <QCustomPlot/src/datacontainer.h>

/** Defines an iterator that can be reasonably wrapped to Python */
template<typename T>
class QCPDataContainerIterator
{
public:
    QCPDataContainerIterator(QCPDataContainer<T> *container) :
        m_pContainer(container), m_Iter(container->begin()) {}
    QCPDataContainerIterator(QCPDataContainer<T> *container, typename QCPDataContainer<T>::iterator itr) :
        m_pContainer(container), m_Iter(itr) {}
    QCPDataContainerIterator(QCPDataContainer<T> *container, typename QCPDataContainer<T>::const_iterator itr) :
        m_pContainer(container), m_Iter(const_cast<typename QCPDataContainer<T>::iterator>(itr)) {}

    T *next() noexcept
    {
        // NULL if we're at the end or current item and advance iterator
        return (m_Iter == m_pContainer->end()) ? nullptr : &(*m_Iter++);
    }

    T *get() noexcept
    {
        // NULL if we're at the end or current item
        return (m_Iter == m_pContainer->end()) ? nullptr : &(*m_Iter);
    }

    typename QCPDataContainer<T>::iterator iterator() const noexcept
    {
        return m_Iter;
    }

protected:
    QCPDataContainer<T> *m_pContainer;
    typename QCPDataContainer<T>::iterator m_Iter;
};

#endif  // __QCUSTOMPLOT_SIP_DATACONTAINER_H
